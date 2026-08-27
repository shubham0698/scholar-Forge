---
name: ui-ux-pro-max
description: Codified design systems, color palettes, typography rules, mesh gradients, glassmorphism templates, and UX guidelines to generate professional-grade interfaces.
---

# UI/UX Pro Max Design Guidelines

This file defines the codified design intelligence guidelines for building premium, high-converting, and accessible user interfaces.

## 1. Typography & Hierarchy
- **Primary Typeface**: `Inter` or system-ui for high legibility body paragraphs.
- **Heading Typeface**: `Outfit`, `Playfair Display`, or `Cabinet Grotesk` for premium branding weight.
- **Font Scale**: 
  - `h1`: `3.2rem` (line-height: 1.1)
  - `h2`: `2.2rem` (line-height: 1.2)
  - `h3`: `1.5rem` (line-height: 1.25)
  - `Body`: `0.92rem` (line-height: 1.65)
  - `Caption`: `0.78rem` (line-height: 1.4)

## 2. Color System (Tailored HSL & Gradients)
- **Primary Base**: Electric Indigo (`hsl(238, 83%, 66%)` or `#6366f1`).
- **Dark Neutral**: Deep Sapphire Slate (`hsl(222, 47%, 11%)` or `#0f172a`).
- **Light Neutral**: Clean Slate Grey (`hsl(210, 40%, 98%)` or `#f8fafc`).
- **Card Background**: Semi-translucent white (`rgba(255, 255, 255, 0.85)`).
- **Gradients**: Linear blends matching `linear-gradient(135deg, var(--primary), var(--primary-dark))` and mesh backgrounds matching `radial-gradient(circle at 30% 30%, rgba(99, 102, 241, 0.15), transparent)`.

## 3. Glassmorphism & Depth
- **Blur Density**: Always use `backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);`.
- **Card Border**: Subtle transparent borders: `border: 1px solid rgba(255, 255, 255, 0.45);`.
- **Shadow Offset**: Combine small card drop shadows with soft indigo glowing colors on hover: `box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05), 0 0 24px rgba(99, 102, 241, 0.15);`.

## 4. UI Layout, Spacing & Alignment
- **Grid Systems**: Always use standard bento grids or card grids with `gap: 1.5rem` or `gap: 2rem`.
- **Paddings**: Form inputs and text fields should have standard internal padding: `0.7rem 1rem`.
- **Margins**: Section layout blocks should maintain consistent bottom margins: `margin-bottom: 2.5rem` or `5rem`.

## 5. Micro-Animations & Interactivity
- **Active Click State**: Scale down elements when pressed: `transform: scale(0.98); transition: transform 0.15s ease;`.
- **Hover Scale Lift**: Smooth translation vectors: `transform: translateY(-4px) scale(1.01);`.
- **Dropdown Transitions**: Height-based slide-down menus using `max-height` transitions instead of binary toggles.

## 6. Accessibility & Usability (UX)
- **Contrast Ratios**: Body text must maintain contrast of at least 4.5:1 against light neutral grids.
- **Touch Target Density**: Interactive button grids must be at least `44px` in height or width.
- **Status Badges**: Alert badges must utilize HSL backgrounds (e.g. green: `rgba(16, 185, 129, 0.1)`, red: `rgba(239, 68, 68, 0.1)`).
