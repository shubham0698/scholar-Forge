"""
ScholarForge Local Backup & Restore Manager
Provides snapshot generation, automated pre-restore safety backups,
ZIP package archival, and atomic data restore functionality.
"""

import os
import json
import zipfile
import sqlite3
import shutil
from datetime import datetime
from extensions import db
from models import User, Paper, Payment, Certificate

BACKUP_DIR = os.path.join(os.getcwd(), 'backups')
UPLOADS_DIR = os.path.join(os.getcwd(), 'uploads')
CERTS_DIR = os.path.join(os.getcwd(), 'static', 'certificates')
QRCODES_DIR = os.path.join(os.getcwd(), 'static', 'qrcodes')


def ensure_backup_dir():
    """Ensure the backups directory exists with a .gitkeep file."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    gitkeep_path = os.path.join(BACKUP_DIR, '.gitkeep')
    if not os.path.exists(gitkeep_path):
        with open(gitkeep_path, 'w') as f:
            f.write('')


def get_db_path():
    """Get absolute path to active SQLite database."""
    try:
        db_uri = db.engine.url.database
        if db_uri and os.path.isabs(db_uri):
            return db_uri
        elif db_uri:
            return os.path.abspath(db_uri)
    except Exception:
        pass
    
    # Fallback default paths
    instance_db = os.path.join(os.getcwd(), 'instance', 'scholarforge_v3.db')
    if os.path.exists(instance_db):
        return instance_db
    return os.path.join(os.getcwd(), 'scholarforge_v3.db')


def format_size(bytes_num):
    """Format byte size into human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def get_db_stats():
    """Get record counts from current database."""
    try:
        return {
            'users': User.query.count(),
            'papers': Paper.query.count(),
            'payments': Payment.query.count(),
            'certificates': Certificate.query.count(),
        }
    except Exception:
        return {'users': 0, 'papers': 0, 'payments': 0, 'certificates': 0}


def create_backup(creator_username="admin", is_safety=False):
    """
    Creates a full backup ZIP archive containing:
    1. SQLite database snapshot (via sqlite3 backup API)
    2. Uploaded files (uploads/)
    3. Generated certificates (static/certificates/)
    4. QR codes (static/qrcodes/)
    5. manifest.json with metadata & stats

    Returns tuple: (success: bool, zip_filename_or_error: str, manifest: dict)
    """
    ensure_backup_dir()
    db_path = get_db_path()

    if not os.path.exists(db_path):
        return False, f"Database file not found at: {db_path}", None

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    prefix = "pre_restore_safety_" if is_safety else "scholarforge_backup_"
    zip_filename = f"{prefix}{timestamp}.zip"
    zip_path = os.path.join(BACKUP_DIR, zip_filename)

    temp_db_snapshot = os.path.join(BACKUP_DIR, f"temp_snapshot_{timestamp}.db")

    try:
        # Step 1: Create atomic SQLite DB snapshot
        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(temp_db_snapshot)
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()

        # Step 2: Build manifest metadata
        stats = get_db_stats()
        manifest = {
            'platform': 'ScholarForge Academic Repository',
            'version': '3.0',
            'created_at': datetime.utcnow().isoformat(),
            'creator': creator_username,
            'is_safety_backup': is_safety,
            'stats': stats,
            'db_size_bytes': os.path.getsize(temp_db_snapshot),
        }

        # Step 3: Archive files into ZIP package
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Database
            zipf.write(temp_db_snapshot, arcname='database.db')
            # Manifest
            zipf.writestr('manifest.json', json.dumps(manifest, indent=2))

            # Uploaded manuscript files
            if os.path.exists(UPLOADS_DIR):
                for root, _, files in os.walk(UPLOADS_DIR):
                    for file in files:
                        if file == '.gitkeep':
                            continue
                        full_path = os.path.join(root, file)
                        arcname = os.path.join('uploads', os.path.relpath(full_path, UPLOADS_DIR))
                        zipf.write(full_path, arcname=arcname)

            # Certificate PDFs
            if os.path.exists(CERTS_DIR):
                for root, _, files in os.walk(CERTS_DIR):
                    for file in files:
                        if file == '.gitkeep':
                            continue
                        full_path = os.path.join(root, file)
                        arcname = os.path.join('certificates', os.path.relpath(full_path, CERTS_DIR))
                        zipf.write(full_path, arcname=arcname)

            # QR Code PNGs
            if os.path.exists(QRCODES_DIR):
                for root, _, files in os.walk(QRCODES_DIR):
                    for file in files:
                        if file == '.gitkeep':
                            continue
                        full_path = os.path.join(root, file)
                        arcname = os.path.join('qrcodes', os.path.relpath(full_path, QRCODES_DIR))
                        zipf.write(full_path, arcname=arcname)

        # Cleanup temporary DB snapshot
        if os.path.exists(temp_db_snapshot):
            os.remove(temp_db_snapshot)

        return True, zip_filename, manifest

    except Exception as e:
        if os.path.exists(temp_db_snapshot):
            os.remove(temp_db_snapshot)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False, str(e), None


def restore_backup(zip_file_or_path, creator_username="admin"):
    """
    Restores platform state from a backup ZIP archive.
    1. Creates automatic safety backup of current state.
    2. Disconnects SQLite engine.
    3. Overwrites DB and restores uploaded files & certificates.

    Returns tuple: (success: bool, message: str, manifest: dict)
    """
    ensure_backup_dir()
    db_path = get_db_path()

    # Step 1: Create automatic safety pre-restore backup
    safety_ok, safety_msg, _ = create_backup(creator_username=creator_username, is_safety=True)
    if not safety_ok:
        return False, f"Failed to create pre-restore safety backup: {safety_msg}", None

    temp_zip_path = None
    if isinstance(zip_file_or_path, str):
        target_zip = os.path.join(BACKUP_DIR, os.path.basename(zip_file_or_path))
        if not os.path.exists(target_zip):
            target_zip = zip_file_or_path
        if not os.path.exists(target_zip):
            return False, f"Backup file not found: {zip_file_or_path}", None
    else:
        # Uploaded file stream
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        temp_zip_path = os.path.join(BACKUP_DIR, f"temp_upload_restore_{timestamp}.zip")
        zip_file_or_path.save(temp_zip_path)
        target_zip = temp_zip_path

    try:
        # Step 2: Validate ZIP structure & manifest
        with zipfile.ZipFile(target_zip, 'r') as zipf:
            namelist = zipf.namelist()
            if 'database.db' not in namelist and 'db_snapshot.db' not in namelist:
                return False, "Invalid backup package: Missing database.db snapshot", None

            manifest = None
            if 'manifest.json' in namelist:
                manifest_data = zipf.read('manifest.json')
                manifest = json.loads(manifest_data.decode('utf-8'))

            # Step 3: Dispose active SQLAlchemy connections
            db.session.remove()
            db.engine.dispose()

            # Step 4: Extract database snapshot
            db_member = 'database.db' if 'database.db' in namelist else 'db_snapshot.db'
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            with open(db_path, 'wb') as db_out:
                db_out.write(zipf.read(db_member))

            # Step 5: Restore uploaded manuscript files
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            for member in namelist:
                if member.startswith('uploads/') and not member.endswith('/'):
                    rel_path = member[len('uploads/'):]
                    dest_path = os.path.join(UPLOADS_DIR, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, 'wb') as out_f:
                        out_f.write(zipf.read(member))

            # Step 6: Restore certificate PDFs
            os.makedirs(CERTS_DIR, exist_ok=True)
            for member in namelist:
                if member.startswith('certificates/') and not member.endswith('/'):
                    rel_path = member[len('certificates/'):]
                    dest_path = os.path.join(CERTS_DIR, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, 'wb') as out_f:
                        out_f.write(zipf.read(member))

            # Step 7: Restore QR codes
            os.makedirs(QRCODES_DIR, exist_ok=True)
            for member in namelist:
                if member.startswith('qrcodes/') and not member.endswith('/'):
                    rel_path = member[len('qrcodes/'):]
                    dest_path = os.path.join(QRCODES_DIR, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, 'wb') as out_f:
                        out_f.write(zipf.read(member))

        if temp_zip_path and os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)

        return True, "Backup successfully restored!", manifest

    except Exception as e:
        if temp_zip_path and os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        return False, f"Restore failed: {str(e)}", None


def list_backups():
    """
    Scans backups/ directory and returns list of backup metadata objects
    sorted by creation time descending.
    """
    ensure_backup_dir()
    backups = []
    if not os.path.exists(BACKUP_DIR):
        return backups

    for file in os.listdir(BACKUP_DIR):
        if not file.endswith('.zip'):
            continue

        full_path = os.path.join(BACKUP_DIR, file)
        size_bytes = os.path.getsize(full_path)
        mtime = datetime.fromtimestamp(os.path.getmtime(full_path))

        manifest = None
        try:
            with zipfile.ZipFile(full_path, 'r') as zipf:
                if 'manifest.json' in zipf.namelist():
                    manifest_raw = zipf.read('manifest.json')
                    manifest = json.loads(manifest_raw.decode('utf-8'))
        except Exception:
            pass

        created_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
        is_safety = file.startswith('pre_restore_safety_') or (manifest and manifest.get('is_safety_backup'))
        creator = manifest.get('creator', 'Admin') if manifest else 'Admin'
        stats = manifest.get('stats', {}) if manifest else {}

        backups.append({
            'filename': file,
            'filepath': full_path,
            'size_bytes': size_bytes,
            'size_formatted': format_size(size_bytes),
            'created_at': created_str,
            'creator': creator,
            'is_safety': is_safety,
            'users_count': stats.get('users', '-'),
            'papers_count': stats.get('papers', '-'),
            'payments_count': stats.get('payments', '-'),
            'certs_count': stats.get('certificates', '-'),
        })

    # Sort newest first
    backups.sort(key=lambda b: b['filename'], reverse=True)
    return backups


def delete_backup(filename):
    """Safely deletes a backup ZIP file from backups/ directory."""
    ensure_backup_dir()
    safe_filename = os.path.basename(filename)
    full_path = os.path.join(BACKUP_DIR, safe_filename)

    if not safe_filename.endswith('.zip'):
        return False, "Invalid file format."

    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            return True, f"Backup {safe_filename} deleted successfully."
        except Exception as e:
            return False, f"Failed to delete file: {str(e)}"
    return False, "Backup file not found."
