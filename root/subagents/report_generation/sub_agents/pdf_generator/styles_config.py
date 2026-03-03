from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

# Accenture Brand Colors
ACCENTURE_PURPLE = colors.HexColor("#A100FF")
ACCENTURE_NAVY = colors.HexColor("#004691")
ACCENTURE_LIGHT_PURPLE = colors.HexColor("#C5A3FF")
ACCENTURE_GRAY = colors.HexColor("#5B5B5B")
ACCENTURE_LIGHT_GRAY = colors.HexColor("#DDDDDD")
ACCENTURE_BG_LIGHT = colors.HexColor("#F9F9F9")

def get_styles():
    """
    Returns a dictionary of ReportLab ParagraphStyle objects configured
    for Accenture-branded report generation.
    """
    styles = getSampleStyleSheet()

    return {
        # Report Title (Header - Large, 18-20pt)
        "title_style": ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=20,
            fontName='Helvetica-Bold',
            textColor=ACCENTURE_NAVY,
            alignment=TA_LEFT,
            spaceAfter=5,
            spaceBefore=5
        ),
        
        # Section Headers (14-16pt, Navy)
        "section_header_style": ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=ACCENTURE_NAVY,
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=10,
            keepWithNext=True
        ),
        
        # Sub-section Headers (12-13pt)
        "subsection_header_style": ParagraphStyle(
            'SubSectionHeader',
            parent=styles['Heading3'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=ACCENTURE_NAVY,
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True
        ),
        
        # Chart/Figure Titles (11-12pt, Bold)
        "chart_title_style": ParagraphStyle(
            'ChartTitle',
            parent=styles['Heading3'],
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceBefore=10,
            spaceAfter=5
        ),
        
        # Body Text (10-11pt, Justified for clean report appearance)
        "body_style": ParagraphStyle(
            'BodyText',
            parent=styles['BodyText'],
            fontSize=10,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_JUSTIFY,
            leading=12,
            spaceAfter=6,
            spaceBefore=2
        ),
        
        # Bullet Points / Lists (10pt, Left-aligned)
        "bullet_style": ParagraphStyle(
            'BulletText',
            parent=styles['BodyText'],
            fontSize=10,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_LEFT,
            leading=14,
            spaceBefore=2,   
            spaceAfter=5,
            leftIndent=20,
            bulletIndent=10
        ),
        
        # Image/Chart Captions (9-10pt, Italic, Gray, Centered)
        "caption_style": ParagraphStyle(
            'FigureCaption',
            parent=styles['Italic'],
            fontSize=9,
            fontName='Helvetica-Oblique',
            textColor=ACCENTURE_GRAY,
            alignment=TA_CENTER,
            spaceBefore=5,
            spaceAfter=10
        ),
        
        # Source/Attribution Text (8-9pt, Small Gray)
        "source_style": ParagraphStyle(
            'SourceText',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=ACCENTURE_GRAY,
            alignment=TA_LEFT,
            spaceBefore=3,
            spaceAfter=8
        ),
        
        # Callout/Highlight Box Text (10pt, with background)
        "callout_style": ParagraphStyle(
            'CalloutText',
            parent=styles['BodyText'],
            fontSize=10,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_LEFT,
            leading=14,
            spaceAfter=10,
            spaceBefore=10,
            leftIndent=12,
            rightIndent=12,
            borderWidth=1,
            borderColor=ACCENTURE_LIGHT_PURPLE,
            borderRadius=4,
            borderPadding=10,
            backColor=ACCENTURE_BG_LIGHT
        ),
        
        # Executive Summary / Key Metrics (Left, Emphasized)
        "executive_summary_style": ParagraphStyle(
            'ExecutiveSummary',
            parent=styles['BodyText'],
            fontSize=11,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_LEFT,
            leading=16,
            spaceAfter=13,
            spaceBefore=10,
            leftIndent=40,
            rightIndent=40
        ),
        
        # Header Text (Small, for date range, confidential tag)
        "header_small_style": ParagraphStyle(
            'HeaderSmall',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=ACCENTURE_GRAY,
            alignment=TA_RIGHT,
            spaceAfter=0
        ),
        
        # Footer Text (Small, for page numbers)
        "footer_style": ParagraphStyle(
            'FooterText',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=ACCENTURE_GRAY,
            alignment=TA_CENTER,
            spaceAfter=0
        ),
        
        # Business Insight Text (Connected to metrics)
        "insight_style": ParagraphStyle(
            'InsightText',
            parent=styles['BodyText'],
            fontSize=10,
            fontName='Helvetica-Oblique',
            textColor=ACCENTURE_NAVY,
            alignment=TA_LEFT,
            leading=14,
            spaceAfter=10,
            spaceBefore=7,
            leftIndent=15,
            bulletIndent=10,
            bulletFontName='ZapfDingbats',
            bulletText='➤'
        ),
        
        # Table Header Style
        "table_header_style": ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=colors.white,
            alignment=TA_CENTER,
            leading=12,
            wordWrap='CJK'
        ),
        
        # Table Cell Style
        "table_cell_style": ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_CENTER,
            leading=11,
            wordWrap='CJK' 
        )
    }


def get_page_settings():
    """
    Returns page dimensions, margins, and available width for content.
    Margins set to 1 inch (72 points) on all sides as per requirements.
    """
    page_width = letter[0]   # 612 points
    page_height = letter[1]  # 792 points
    
    # 1 inch = 72 points (ReportLab uses points: 1 inch = 72 points)
    margins = {
        "left": 72,      # 1 inch
        "right": 72,     # 1 inch
        "top": 72,       # 1 inch
        "bottom": 72     # 1 inch
    }
    
    available_width = page_width - margins["left"] - margins["right"]
    available_height = page_height - margins["top"] - margins["bottom"]
    
    return page_width, page_height, margins, available_width, available_height


def get_image_settings():
    """
    Returns configuration for image sizing in the report.
    """
    _, _, _, available_width, _ = get_page_settings()
    
    return {
        "max_width_ratio": 1.0,  # Changed from 0.8 to 1.0 - USE FULL WIDTH
        "max_width": available_width * 1.0,  # Changed from 0.8 to 1.0
        "max_height": 450,  # Increased from 400 to 450 for taller images
        "default_spacing_before": 12,
        "default_spacing_after": 6
    }


def get_header_footer_settings():
    """
    Returns configuration for header and footer layout.
    """
    return {
        "header_height": 50,  # Height reserved for header (0.5-0.7cm ≈ 14-20pts)
        "footer_height": 40,  # Height reserved for footer
        "brand_bar_height": 18,  # Thin colored strip height (~0.5cm)
        "brand_bar_color": ACCENTURE_PURPLE,
        "logo_max_width": 120,  # Maximum logo width in points
        "logo_max_height": 30,  # Maximum logo height in points
        "logo_padding": 10  # Clear space around logo
    }


def get_brand_colors():
    """
    Returns Accenture brand color palette for charts and visualizations.
    """
    return {
        "primary": ACCENTURE_PURPLE,
        "secondary": ACCENTURE_NAVY,
        "accent": ACCENTURE_LIGHT_PURPLE,
        "gray": ACCENTURE_GRAY,
        "light_gray": ACCENTURE_LIGHT_GRAY,
        "background": ACCENTURE_BG_LIGHT,
        # Chart color palette
        "chart_colors": [
            ACCENTURE_PURPLE,
            ACCENTURE_NAVY,
            ACCENTURE_LIGHT_PURPLE,
            colors.HexColor("#00A3E0"),  # Bright blue
            colors.HexColor("#6CC24A"),  # Green
            colors.HexColor("#FF6B35"),  # Orange
        ]
    }


def get_table_styles():
    """
    Returns common table styling configurations.
    """
    from reportlab.platypus import TableStyle
    
    return {
        "default_table_style": TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), ACCENTURE_NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, ACCENTURE_LIGHT_GRAY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ACCENTURE_BG_LIGHT]),
        ]),
        
        "minimal_table_style": TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), ACCENTURE_PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            
            # Data rows - no grid, just spacing
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Bottom border only
            ('LINEBELOW', (0, 0), (-1, 0), 2, ACCENTURE_NAVY),
        ])
    }


def add_page_decor(canvas, doc, brand_colors, page_width, page_height, margins,
                   header_footer_settings, accenture_logo_data=None, cora_logo_data=None,
                   context="Campaign Performance Report", 
                   short_title="CPR – Q4 2025", 
                   date_range="Q4 2025"):
    """
    Draws header and footer on each page with Accenture branding and dual logos.
    This function can be used directly in doc.build() callbacks.
    
    Args:
        canvas: ReportLab canvas object
        doc: SimpleDocTemplate document object
        brand_colors: Dictionary from get_brand_colors()
        page_width: Page width in points
        page_height: Page height in points
        margins: Dictionary with margin settings
        header_footer_settings: Dictionary from get_header_footer_settings()
        accenture_logo_data: BytesIO object containing Accenture logo image (optional)
        cora_logo_data: BytesIO object containing Cora logo image (optional)
        context: Full report title for header
        short_title: Short form for footer center
        date_range: Date range text (e.g., "Q4 2025")
    """
    canvas.saveState()
    
    # Get settings
    bar_height = header_footer_settings['brand_bar_height']
    brand_color = header_footer_settings['brand_bar_color']
    header_height = header_footer_settings["header_height"]
    # ===== HEADER SECTION =====
    
    # Brand bar at the very top (thin strip ~0.5-0.7cm)
    canvas.setFillColor(brand_color)
    canvas.rect(
        0, 
        page_height - bar_height, 
        page_width, 
        bar_height, 
        fill=True, 
        stroke=False
    )
    
    # Header text position (below brand bar)
    # Position title slightly below the logos, aligned to center
    header_y = page_height - bar_height - (header_height - bar_height) / 2 # Adjust spacing as needed
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(colors.black)
    canvas.drawCentredString(page_width / 2, header_y, context)

    
    # ===== LEFT LOGO: ACCENTURE =====
    if accenture_logo_data:
        try:
            # Reset BytesIO position for reading
            accenture_logo_data.seek(0)
            
            # Save the BytesIO to a temporary file to use with canvas.drawImage
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_file.write(accenture_logo_data.getvalue())
                temp_filename = temp_file.name
            
            # Get logo dimensions (smaller size - 50% of original max size)
            logo_max_width = header_footer_settings['logo_max_width'] * 0.5
            logo_max_height = header_footer_settings['logo_max_height'] * 0.5
            
            # Position logo left-aligned with the left margin (with padding)
            logo_x = page_width * 0.02
            logo_y = page_height - margins['top']+12
            
            # Draw logo on canvas
            canvas.drawImage(
                temp_filename,
                logo_x,
                logo_y,
                width=logo_max_width,
                height=logo_max_height,
                preserveAspectRatio=True,
                mask='auto'
            )
            
            # Clean up temporary file
            os.unlink(temp_filename)
            
        except Exception as e:
            print(f"⚠️ Failed to render Accenture logo on page {doc.page}: {e}")
    
    # ===== RIGHT LOGO: CORA =====
    if cora_logo_data:
        try:
            # Reset BytesIO position for reading
            cora_logo_data.seek(0)
            
            # Save the BytesIO to a temporary file to use with canvas.drawImage
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_file.write(cora_logo_data.getvalue())
                temp_filename = temp_file.name
            
            # Get logo dimensions (smaller size - 50% of original max size)
            logo_max_width = header_footer_settings['logo_max_width'] * 0.5
            logo_max_height = header_footer_settings['logo_max_height'] * 0.5
            
            # Position logo right-aligned with the right margin
            # The right edge of the logo will be at page_width - margins['right']
            logo_x = page_width * 0.98 - logo_max_width
            logo_y = page_height - margins['top']+12
            
            # Draw logo on canvas
            canvas.drawImage(
                temp_filename,
                logo_x,
                logo_y,
                width=logo_max_width,
                height=logo_max_height,
                preserveAspectRatio=True,
                mask='auto'
            )
            
            # Clean up temporary file
            os.unlink(temp_filename)
            
        except Exception as e:
            print(f"⚠️ Failed to render Cora logo on page {doc.page}: {e}")
    
    # Header Right: Date range + "Confidential"
    # Move Confidential line just below brand bar
    conf_y = page_height - bar_height - 10
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    conf_text = f"{date_range}  |  Confidential"
    canvas.drawString(page_width * 0.85, conf_y, conf_text)


    
    
    # ===== FOOTER SECTION =====
    
    footer_y = margins['bottom'] - 20
    
    # Footer Left: Page X
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    page_num_text = f"Page {doc.page}"
    canvas.drawString(margins['left'], footer_y, page_num_text)
    
    # Footer Center: Short Title
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(page_width / 2, footer_y, short_title)
    
    canvas.restoreState()
    # ===== PAGE BORDER =====
    # Draw a border around the page content area (inside margins)
    #Cnvas.setStrokeColor(ACCENTURE_LIGHT_GRAY)  # Light gray border
    #anvas.setLineWidth(1)  # Border thickness
    #anvas.rect(
     #  margins['left'],  # x position (left margin)
      # margins['bottom'],  # y position (bottom margin)
       #page_width - margins['left'] - margins['right'],  # width
    #   page_height - margins['top'] - margins['bottom'],  # height
     #  fill=False,  # Don't fill, just outline
      # stroke=True
   #)
    
    # Get settings
   #bar_height = header_footer_settings['brand_bar_height']
   #brand_color = header_footer_settings['brand_bar_color']