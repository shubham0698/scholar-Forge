from flask import Blueprint, render_template, request, abort, flash, redirect, url_for, send_file
from flask_login import current_user
from models import db, Paper, User, Certificate, Payment

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    public_papers_query = Paper.query.join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    )
    total_papers = public_papers_query.count()
    total_users = User.query.count()
    total_certs = Certificate.query.join(Paper, Certificate.paper_id == Paper.id).join(Payment, Paper.id == Payment.paper_id).filter(Payment.status == 'completed').count()
    recent_papers = public_papers_query.order_by(Paper.created_at.desc()).limit(3).all()
    
    categories = db.session.query(Paper.category).join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    ).distinct().limit(6).all()
    categories = [c[0] for c in categories] if categories else ['Computer Science', 'Biotechnology', 'Electrical Engineering', 'Physics']
    
    return render_template(
        'index.html',
        total_papers=total_papers,
        total_users=total_users,
        total_certs=total_certs,
        recent_papers=recent_papers,
        categories=categories
    )

@public_bp.route('/explore')
def explore():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    query = Paper.query.join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    )
    if category:
        query = query.filter(Paper.category == category)
    papers = query.order_by(Paper.created_at.desc()).all()
    
    categories = db.session.query(Paper.category).join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    ).distinct().all()
    categories = [c[0] for c in categories]
    return render_template('explore.html', papers=papers, categories=categories, selected_category=category)

@public_bp.route('/paper/<int:id>')
def paper_detail(id):
    paper = Paper.query.get_or_404(id)
    
    is_paid = bool(paper.payment and paper.payment.status == 'completed')
    is_author_or_admin = current_user.is_authenticated and (paper.user_id == current_user.id or current_user.is_admin)

    # Private papers restricted to author & admin
    if paper.visibility == 'private':
        if not is_author_or_admin:
            flash('This research paper is marked as private by the author.')
            return redirect(url_for('public.explore'))

    # Unpaid / Pending payment papers restricted to author & admin
    if not is_paid:
        if not is_author_or_admin:
            flash('This research paper is awaiting publication payment and is not yet publicly accessible.')
            return redirect(url_for('public.explore'))

    # Increment view count
    paper.views_count = (paper.views_count or 0) + 1
    db.session.commit()
    
    guide = paper.guides[0] if paper.guides else None
    contributors = paper.contributors
    return render_template('paper_detail.html', paper=paper, guide=guide, contributors=contributors, payment_pending=(not is_paid))

@public_bp.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if query:
        results = Paper.query.join(User, Paper.user_id == User.id).join(Payment, Paper.id == Payment.paper_id).filter(
            (Paper.visibility == 'public'),
            (Paper.status == 'approved'),
            (Payment.status == 'completed'),
            (Paper.title.ilike(f'%{query}%')) |
            (Paper.abstract.ilike(f'%{query}%')) |
            (Paper.keywords.ilike(f'%{query}%')) |
            (Paper.category.ilike(f'%{query}%')) |
            (User.username.ilike(f'%{query}%')) |
            (User.institution.ilike(f'%{query}%'))
        ).order_by(Paper.created_at.desc()).all()
    else:
        results = []
    return render_template('search.html', query=query, results=results)

@public_bp.route('/sitemap.xml')
def sitemap():
    from flask import Response, url_for
    papers = Paper.query.join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    ).all()
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    static_urls = [
        (url_for('public.index', _external=True), '1.0', 'daily'),
        (url_for('public.explore', _external=True), '0.9', 'daily'),
        (url_for('public.about', _external=True), '0.7', 'monthly'),
        (url_for('public.contact', _external=True), '0.7', 'monthly'),
        (url_for('public.verify_lookup', _external=True), '0.8', 'weekly'),
        (url_for('public.terms', _external=True), '0.5', 'monthly'),
        (url_for('public.privacy', _external=True), '0.5', 'monthly'),
    ]
    
    for url, priority, freq in static_urls:
        xml.append(f'  <url><loc>{url}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>')
        
    for p in papers:
        paper_url = url_for('public.paper_detail', id=p.id, _external=True)
        lastmod = p.created_at.strftime('%Y-%m-%d')
        xml.append(f'  <url><loc>{paper_url}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.95</priority></url>')
        
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')

@public_bp.route('/robots.txt')
def robots():
    from flask import Response, url_for
    sitemap_url = url_for('public.sitemap', _external=True)
    content = f"""User-agent: *
Allow: /
Allow: /explore
Allow: /paper/
Allow: /verify/
Allow: /about
Allow: /contact
Allow: /terms
Allow: /privacy
Disallow: /admin/
Disallow: /dashboard
Disallow: /upload

Sitemap: {sitemap_url}
"""
    return Response(content, mimetype='text/plain')

@public_bp.route('/verify/<certificate_id>')
def verify_certificate(certificate_id):
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper

    is_paid = bool(paper.payment and paper.payment.status == 'completed')
    is_author_or_admin = current_user.is_authenticated and (paper.user_id == current_user.id or current_user.is_admin)

    if not is_paid and not is_author_or_admin:
        flash('Certificate is inactive as publication payment is pending.')
        return redirect(url_for('public.index'))

    author = paper.author
    guide = paper.guides[0] if paper.guides else None
    return render_template(
        'verify.html',
        certificate=cert,
        paper=paper,
        author=author,
        guide=guide,
        payment_pending=(not is_paid)
    )

@public_bp.route('/public-download-certificate/<certificate_id>')
def public_download_certificate(certificate_id):
    from certificate_generator import generate_certificate_pdf
    from datetime import datetime
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper

    is_paid = bool(paper.payment and paper.payment.status == 'completed')
    is_author_or_admin = current_user.is_authenticated and (paper.user_id == current_user.id or current_user.is_admin)

    if not is_paid and not is_author_or_admin:
        flash('Certificate download is unavailable as publication payment is pending.')
        return redirect(url_for('public.index'))

    verify_url = url_for('public.verify_certificate', certificate_id=cert.certificate_id, _external=True)
    paper_url = url_for('public.paper_detail', id=paper.id, _external=True)
    guide = paper.guides[0] if paper.guides else None

    pdf_stream = generate_certificate_pdf(
        certificate_id=cert.certificate_id,
        paper_title=paper.title,
        author_name=paper.author.username,
        publication_id=paper.publication_id,
        category=paper.category,
        institution=paper.author.institution or '',
        guide_name=guide.name if guide else '',
        issue_date=cert.issue_date or datetime.utcnow(),
        verify_url=verify_url,
        qr_code_path=cert.qr_code_path,
        cert_type=getattr(cert, 'cert_type', 'publication') or 'publication',
        doi=paper.doi,
        paper_url=paper_url
    )

    return send_file(
        pdf_stream,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ScholarForge_Certificate_{certificate_id}.pdf",
    )

@public_bp.route('/verify', methods=['GET', 'POST'])
def verify_lookup():
    if request.method == 'POST':
        cert_id = request.form.get('certificate_id', '').strip()
        if cert_id:
            cert = Certificate.query.filter_by(certificate_id=cert_id).first()
            if cert:
                return redirect(url_for('public.verify_certificate', certificate_id=cert_id))
            else:
                flash('No certificate found with that ID. Please check and try again.')
        else:
            flash('Please enter a certificate ID.')
    return render_template('verify_lookup.html')

@public_bp.route('/terms')
def terms():
    return render_template('terms.html')

@public_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')

@public_bp.route('/about')
def about():
    total_papers = Paper.query.join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    ).count()
    total_users = User.query.count()
    total_certs = Certificate.query.join(Paper, Certificate.paper_id == Paper.id).join(Payment, Paper.id == Payment.paper_id).filter(Payment.status == 'completed').count()
    return render_template(
        'about.html',
        total_papers=total_papers,
        total_users=total_users,
        total_certs=total_certs,
    )

@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you for your message! We\'ll get back to you within 24 hours.')
        return redirect(url_for('public.contact'))
    return render_template('contact.html')

@public_bp.route('/oai')
def oai_pmh():
    from flask import Response
    papers = Paper.query.join(Payment, Paper.id == Payment.paper_id).filter(
        Paper.visibility == 'public',
        Paper.status == 'approved',
        Payment.status == 'completed'
    ).all()
    xml_data = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_data.append('<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"')
    xml_data.append('         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
    xml_data.append('         xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd">')
    
    from datetime import datetime
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    xml_data.append(f'  <responseDate>{now_str}</responseDate>')
    xml_data.append('  <request verb="ListRecords" metadataPrefix="oai_dc">http://localhost:5000/oai</request>')
    xml_data.append('  <ListRecords>')
    
    for p in papers:
        xml_data.append('    <record>')
        xml_data.append('      <header>')
        xml_data.append(f'        <identifier>oai:scholarforge.com:{p.id}</identifier>')
        xml_data.append(f'        <datestamp>{p.created_at.strftime("%Y-%m-%d")}</datestamp>')
        xml_data.append('        <setSpec>research</setSpec>')
        xml_data.append('      </header>')
        xml_data.append('      <metadata>')
        xml_data.append('        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"')
        xml_data.append('                   xmlns:dc="http://purl.org/dc/elements/1.1/"')
        xml_data.append('                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
        xml_data.append('                   xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd">')
        
        # Dublin Core fields
        title_escaped = p.title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        abstract_escaped = p.abstract.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        author_escaped = p.author.username.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        category_escaped = p.category.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        keywords_escaped = p.keywords.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        xml_data.append(f'          <dc:title>{title_escaped}</dc:title>')
        xml_data.append(f'          <dc:creator>{author_escaped}</dc:creator>')
        xml_data.append(f'          <dc:subject>{keywords_escaped}</dc:subject>')
        xml_data.append(f'          <dc:description>{abstract_escaped}</dc:description>')
        xml_data.append(f'          <dc:publisher>ScholarForge</dc:publisher>')
        xml_data.append(f'          <dc:date>{p.created_at.strftime("%Y-%m-%d")}</dc:date>')
        xml_data.append(f'          <dc:type>Text</dc:type>')
        xml_data.append(f'          <dc:format>application/pdf</dc:format>')
        if p.doi:
            xml_data.append(f'          <dc:identifier>doi:{p.doi}</dc:identifier>')
        xml_data.append(f'          <dc:identifier>http://localhost:5000/paper/{p.id}</dc:identifier>')
        xml_data.append(f'          <dc:language>eng</dc:language>')
        xml_data.append(f'          <dc:coverage>{category_escaped}</dc:coverage>')
        
        xml_data.append('        </oai_dc:dc>')
        xml_data.append('      </metadata>')
        xml_data.append('    </record>')
        
    xml_data.append('  </ListRecords>')
    xml_data.append('</OAI-PMH>')
    
    return Response('\n'.join(xml_data), mimetype='application/xml')

