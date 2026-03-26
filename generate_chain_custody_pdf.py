#!/usr/bin/env python3
"""
Generate Chain of Custody Documentation PDF
With flow diagrams and concrete examples
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO

def create_flow_diagram():
    """Create a flow of funds diagram"""
    d = Drawing(500, 200)
    
    # Colors
    wallet_color = colors.HexColor('#3B82F6')  # Blue
    exchange_color = colors.HexColor('#10B981')  # Green
    arrow_color = colors.HexColor('#6B7280')  # Gray
    break_color = colors.HexColor('#EF4444')  # Red
    
    # Box dimensions
    box_w, box_h = 90, 40
    y_center = 100
    
    # Wallet 1 (Your Coinbase)
    d.add(Rect(20, y_center - box_h/2, box_w, box_h, fillColor=exchange_color, strokeColor=colors.black, strokeWidth=1))
    d.add(String(35, y_center - 5, "Coinbase", fontSize=10, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(35, y_center - 18, "(Your Wallet)", fontSize=8, fillColor=colors.white))
    
    # Arrow 1
    d.add(Line(110, y_center, 150, y_center, strokeColor=arrow_color, strokeWidth=2))
    d.add(Polygon([150, y_center, 145, y_center+5, 145, y_center-5], fillColor=arrow_color))
    d.add(String(115, y_center + 12, "Send ETH", fontSize=8, fillColor=arrow_color))
    
    # Bridge / DEX
    d.add(Rect(155, y_center - box_h/2, box_w, box_h, fillColor=colors.HexColor('#8B5CF6'), strokeColor=colors.black, strokeWidth=1))
    d.add(String(175, y_center - 5, "Bridge/DEX", fontSize=10, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(165, y_center - 18, "(Intermediate)", fontSize=8, fillColor=colors.white))
    
    # Chain Break indicator
    d.add(Rect(255, y_center - 30, 40, 60, fillColor=break_color, strokeColor=colors.black, strokeWidth=2))
    d.add(String(258, y_center + 8, "CHAIN", fontSize=8, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(258, y_center - 5, "BREAK", fontSize=8, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(265, y_center - 18, "?", fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'))
    
    # Arrow 2 (broken)
    d.add(Line(295, y_center, 320, y_center, strokeColor=arrow_color, strokeWidth=2, strokeDashArray=[3,3]))
    
    # Unknown Wallet
    d.add(Rect(325, y_center - box_h/2, box_w, box_h, fillColor=colors.HexColor('#F59E0B'), strokeColor=colors.black, strokeWidth=1))
    d.add(String(340, y_center - 5, "Unknown", fontSize=10, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(345, y_center - 18, "Wallet", fontSize=8, fillColor=colors.white))
    
    # Question marks
    d.add(String(430, y_center - 5, "Yours?", fontSize=12, fillColor=break_color, fontName='Helvetica-Bold'))
    d.add(String(425, y_center - 20, "External?", fontSize=12, fillColor=break_color, fontName='Helvetica-Bold'))
    
    # Title
    d.add(String(150, 180, "DIAGRAM 1: Flow of Funds & Chain Break", fontSize=12, fillColor=colors.black, fontName='Helvetica-Bold'))
    
    return d

def create_resolution_diagram():
    """Create a diagram showing resolution outcomes"""
    d = Drawing(500, 280)
    
    # Colors
    mine_color = colors.HexColor('#10B981')  # Green
    external_color = colors.HexColor('#EF4444')  # Red
    pending_color = colors.HexColor('#F59E0B')  # Orange
    
    # Title
    d.add(String(100, 260, "DIAGRAM 2: Chain Break Resolution & Tax Impact", fontSize=12, fillColor=colors.black, fontName='Helvetica-Bold'))
    
    # Pending Review Box (center top)
    d.add(Rect(180, 200, 140, 45, fillColor=pending_color, strokeColor=colors.black, strokeWidth=2))
    d.add(String(195, 225, "PENDING REVIEW", fontSize=10, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(190, 210, "Transfer: 2.5 ETH", fontSize=9, fillColor=colors.white))
    
    # Arrow to "Mark as Mine"
    d.add(Line(200, 200, 120, 150, strokeColor=mine_color, strokeWidth=2))
    d.add(Polygon([120, 150, 125, 158, 130, 152], fillColor=mine_color))
    
    # Arrow to "Mark as External"
    d.add(Line(300, 200, 380, 150, strokeColor=external_color, strokeWidth=2))
    d.add(Polygon([380, 150, 375, 158, 370, 152], fillColor=external_color))
    
    # "Mark as Mine" outcome
    d.add(Rect(30, 90, 180, 55, fillColor=mine_color, strokeColor=colors.black, strokeWidth=1))
    d.add(String(50, 125, "MARKED AS MINE", fontSize=10, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(40, 110, "Creates Linkage Edge", fontSize=9, fillColor=colors.white))
    d.add(String(40, 97, "NO taxable event", fontSize=9, fillColor=colors.white))
    
    # Result of Mine
    d.add(Rect(50, 30, 140, 40, fillColor=colors.HexColor('#D1FAE5'), strokeColor=mine_color, strokeWidth=1))
    d.add(String(60, 52, "Cost Basis Preserved", fontSize=9, fillColor=colors.black))
    d.add(String(60, 38, "Internal Transfer", fontSize=9, fillColor=colors.black))
    
    d.add(Line(120, 90, 120, 70, strokeColor=mine_color, strokeWidth=1))
    d.add(Polygon([120, 70, 115, 78, 125, 78], fillColor=mine_color))
    
    # "Mark as External" outcome
    d.add(Rect(290, 90, 180, 55, fillColor=external_color, strokeColor=colors.black, strokeWidth=1))
    d.add(String(300, 125, "MARKED AS EXTERNAL", fontSize=10, fillColor=colors.white, fontName='Helvetica-Bold'))
    d.add(String(300, 110, "Creates Disposal Event", fontSize=9, fillColor=colors.white))
    d.add(String(300, 97, "TAXABLE - Form 8949", fontSize=9, fillColor=colors.white))
    
    # Result of External
    d.add(Rect(310, 30, 140, 40, fillColor=colors.HexColor('#FEE2E2'), strokeColor=external_color, strokeWidth=1))
    d.add(String(320, 52, "Capital Gain/Loss", fontSize=9, fillColor=colors.black))
    d.add(String(320, 38, "IRS Form 8949 Line", fontSize=9, fillColor=colors.black))
    
    d.add(Line(380, 90, 380, 70, strokeColor=external_color, strokeWidth=1))
    d.add(Polygon([380, 70, 375, 78, 385, 78], fillColor=external_color))
    
    return d

def create_pdf():
    """Generate the complete PDF document"""
    
    doc = SimpleDocTemplate(
        "/app/Chain_of_Custody_Documentation.pdf",
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1E3A8A')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#1E40AF')
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading3'],
        fontSize=13,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#3B82F6')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10,
        leading=16
    )
    
    highlight_style = ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10,
        leading=16,
        backColor=colors.HexColor('#FEF3C7'),
        borderPadding=10
    )
    
    story = []
    
    # Title
    story.append(Paragraph("Chain of Custody System", title_style))
    story.append(Paragraph("Crypto Bag Tracker - Tax Documentation", styles['Heading3']))
    story.append(Spacer(1, 20))
    
    # Overview
    story.append(Paragraph("Overview", heading_style))
    story.append(Paragraph(
        "The Chain of Custody system is a 3-layer architecture designed to accurately track cryptocurrency "
        "movements across wallets and exchanges. Its primary purpose is to distinguish between <b>internal transfers</b> "
        "(moving crypto between your own wallets) and <b>external transfers</b> (sending crypto to someone else), "
        "which has critical tax implications.",
        body_style
    ))
    
    story.append(Spacer(1, 10))
    
    # Why it matters
    story.append(Paragraph("Why This Matters for Taxes", subheading_style))
    
    tax_data = [
        ['Transfer Type', 'Tax Treatment', 'IRS Impact'],
        ['Internal (Your Wallet → Your Wallet)', 'NOT taxable', 'Cost basis carries over'],
        ['External (Your Wallet → Someone Else)', 'TAXABLE disposal', 'Capital gain/loss on Form 8949'],
    ]
    
    tax_table = Table(tax_data, colWidths=[2.2*inch, 1.8*inch, 2*inch])
    tax_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#D1FAE5')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#FEE2E2')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    story.append(tax_table)
    story.append(Spacer(1, 20))
    
    # Diagram 1
    story.append(Paragraph("Flow of Funds & Chain Breaks", heading_style))
    story.append(Paragraph(
        "When you send cryptocurrency through bridges, DEXs, or complex DeFi protocols, the system may lose "
        "track of whether the receiving wallet belongs to you. This creates a <b>Chain Break</b> - an unlinked "
        "transfer that requires your input to resolve.",
        body_style
    ))
    story.append(Spacer(1, 10))
    story.append(create_flow_diagram())
    story.append(Spacer(1, 20))
    
    # Diagram 2
    story.append(Paragraph("Resolution Process & Tax Impact", heading_style))
    story.append(Paragraph(
        "When a chain break is detected, the transfer appears in your <b>Review Queue</b>. You must decide: "
        "Is this destination wallet yours (internal transfer) or someone else's (external/taxable)?",
        body_style
    ))
    story.append(Spacer(1, 10))
    story.append(create_resolution_diagram())
    
    story.append(PageBreak())
    
    # Concrete Example
    story.append(Paragraph("Concrete Example: ETH Bridge Transfer", heading_style))
    story.append(Paragraph(
        "Let's walk through a real-world scenario where a chain break occurs and how it gets resolved.",
        body_style
    ))
    story.append(Spacer(1, 15))
    
    # Scenario Setup
    story.append(Paragraph("Scenario Setup", subheading_style))
    
    scenario_data = [
        ['Detail', 'Value'],
        ['Asset', '2.5 ETH'],
        ['Original Purchase', 'March 2024 @ $3,200/ETH ($8,000 total cost basis)'],
        ['Current Price', '$3,800/ETH ($9,500 current value)'],
        ['Action', 'Bridge from Ethereum mainnet to Arbitrum'],
    ]
    
    scenario_table = Table(scenario_data, colWidths=[1.8*inch, 4.2*inch])
    scenario_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366F1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#F3F4F6')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(scenario_table)
    story.append(Spacer(1, 20))
    
    # Step by step
    story.append(Paragraph("Step-by-Step Flow", subheading_style))
    
    steps = [
        ("<b>Step 1: You Initiate Bridge</b><br/>"
         "You send 2.5 ETH from your Coinbase Wallet (0x1234...abcd) through an Arbitrum bridge contract."),
        
        ("<b>Step 2: Bridge Processes Transfer</b><br/>"
         "The bridge receives your ETH on mainnet and mints equivalent ETH on Arbitrum to address 0x9876...wxyz."),
        
        ("<b>Step 3: Chain Break Detected</b><br/>"
         "The system sees ETH left your known wallet (0x1234...abcd) but cannot confirm if 0x9876...wxyz belongs to you. "
         "This transfer is flagged and added to your <b>Review Queue</b>."),
        
        ("<b>Step 4: You Review the Transfer</b><br/>"
         "In the Review Queue, you see: 'Transfer of 2.5 ETH to 0x9876...wxyz - Is this your wallet?'"),
    ]
    
    for step in steps:
        story.append(Paragraph(step, body_style))
        story.append(Spacer(1, 5))
    
    story.append(Spacer(1, 15))
    
    # Decision Point
    story.append(Paragraph("Decision Point: Two Possible Outcomes", subheading_style))
    
    # Option A
    story.append(Paragraph("<b>Option A: You Mark as 'MINE' (Internal Transfer)</b>", body_style))
    option_a_data = [
        ['What Happens', 'Tax Impact'],
        ['System creates linkage edge: 0x1234...abcd ↔ 0x9876...wxyz', 'NO taxable event'],
        ['Both wallets now recognized as belonging to you', 'Cost basis of $8,000 preserved'],
        ['Future transfers between these wallets are auto-linked', 'Will report properly on future sales'],
    ]
    
    option_a_table = Table(option_a_data, colWidths=[3.5*inch, 2.5*inch])
    option_a_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D1FAE5')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECFDF5')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(option_a_table)
    story.append(Spacer(1, 15))
    
    # Option B
    story.append(Paragraph("<b>Option B: You Mark as 'EXTERNAL' (Taxable Disposal)</b>", body_style))
    option_b_data = [
        ['What Happens', 'Tax Impact'],
        ['System records this as a disposal/sale event', 'TAXABLE capital gain'],
        ['Proceeds = Fair Market Value at time of transfer', 'Proceeds: $9,500 (2.5 × $3,800)'],
        ['Form 8949 line item is generated', 'Cost Basis: $8,000'],
        ['Reported as short-term or long-term based on holding period', 'Capital Gain: $1,500'],
    ]
    
    option_b_table = Table(option_b_data, colWidths=[3.5*inch, 2.5*inch])
    option_b_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EF4444')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#FEE2E2')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FEF2F2')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(option_b_table)
    story.append(Spacer(1, 20))
    
    # Form 8949 Example
    story.append(Paragraph("Resulting Form 8949 Entry (If Marked External)", subheading_style))
    
    form_data = [
        ['(a) Description', '(b) Date Acquired', '(c) Date Sold', '(d) Proceeds', '(e) Cost Basis', '(h) Gain/Loss'],
        ['2.5 ETH', '03/15/2024', '11/20/2024', '$9,500.00', '$8,000.00', '$1,500.00'],
    ]
    
    form_table = Table(form_data, colWidths=[1.2*inch, 1*inch, 1*inch, 0.9*inch, 0.9*inch, 0.9*inch])
    form_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(form_table)
    story.append(Spacer(1, 25))
    
    # Key Takeaways
    story.append(Paragraph("Key Takeaways", heading_style))
    
    takeaways = [
        "1. <b>Chain breaks occur</b> when the system cannot verify wallet ownership after complex transactions (bridges, DEXs, etc.)",
        "2. <b>Your input is required</b> to resolve chain breaks - only you know which wallets belong to you.",
        "3. <b>Marking as 'Mine'</b> creates a linkage edge, preserving cost basis and avoiding false taxable events.",
        "4. <b>Marking as 'External'</b> treats the transfer as a disposal, generating a Form 8949 capital gain/loss event.",
        "5. <b>Accuracy matters</b> - incorrect resolutions can lead to overpaying or underpaying taxes.",
    ]
    
    for takeaway in takeaways:
        story.append(Paragraph(takeaway, body_style))
    
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph(
        "<i>This document is for informational purposes. Consult a tax professional for specific advice.</i>",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.gray, alignment=TA_CENTER)
    ))
    
    # Build PDF
    doc.build(story)
    print("PDF generated successfully: /app/Chain_of_Custody_Documentation.pdf")

if __name__ == "__main__":
    create_pdf()
