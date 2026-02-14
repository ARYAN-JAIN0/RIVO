# Invoice Generator

"""
Invoice Generator Service

PHASE-3 EXTENSION: Generate PDF invoices from contract data.
Integrates with Finance Agent for professional invoice creation.

BACKWARD COMPATIBILITY:
- Standalone service, doesn't modify transactional tables directly
- Optional dependency (agents work without it)
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  ReportLab not installed. PDF invoice generation disabled.")
    print("   Install with: pip install reportlab")


# Configuration
BASE_DIR = Path(__file__).resolve().parents[2]
INVOICE_OUTPUT_DIR = BASE_DIR / "invoices"


def generate_invoice_pdf(
    invoice_data: Dict,
    output_path: Optional[Path] = None
) -> Optional[str]:
    """
    Generate a professional PDF invoice.
    
    Args:
        invoice_data: Dictionary containing:
            - invoice_id: int
            - customer_name: str
            - customer_company: str
            - customer_email: str
            - amount: float
            - due_date: str (YYYY-MM-DD)
            - line_items: List[Dict] (optional)
            - notes: str (optional)
        output_path: Custom path, or auto-generate if None
    
    Returns:
        Path to generated PDF, or None if failed
    """
    if not REPORTLAB_AVAILABLE:
        print("❌ ReportLab not available. Cannot generate PDF.")
        return None
    
    # Create output directory
    INVOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate output path
    if output_path is None:
        invoice_id = invoice_data.get('invoice_id', 'UNKNOWN')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = INVOICE_OUTPUT_DIR / f"invoice_{invoice_id}_{timestamp}.pdf"
    
    try:
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )
        
        # Container for elements
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Company header
        elements.append(Paragraph("RevoAI", title_style))
        elements.append(Paragraph(
            "123 AI Street, San Francisco, CA 94102<br/>hello@revoai.com | (555) 123-4567",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Invoice title
        invoice_title = f"INVOICE #{invoice_data.get('invoice_id', 'N/A')}"
        elements.append(Paragraph(invoice_title, styles['Heading1']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Bill To section
        bill_to_data = [
            ['Bill To:', '', 'Invoice Date:', datetime.now().strftime('%B %d, %Y')],
            [invoice_data.get('customer_name', 'N/A'), '', 'Due Date:', invoice_data.get('due_date', 'N/A')],
            [invoice_data.get('customer_company', 'N/A'), '', 'Amount Due:', f"${invoice_data.get('amount', 0):,.2f}"],
            [invoice_data.get('customer_email', 'N/A'), '', '', '']
        ]
        
        bill_to_table = Table(bill_to_data, colWidths=[2.5*inch, 0.5*inch, 1.5*inch, 2*inch])
        bill_to_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(bill_to_table)
        elements.append(Spacer(1, 0.4 * inch))
        
        # Line items
        line_items = invoice_data.get('line_items', [
            {
                'description': 'RevoAI SaaS Platform - Annual Subscription',
                'quantity': 1,
                'unit_price': invoice_data.get('amount', 0),
                'total': invoice_data.get('amount', 0)
            }
        ])
        
        # Line items table
        items_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
        
        for item in line_items:
            items_data.append([
                item.get('description', ''),
                str(item.get('quantity', 1)),
                f"${item.get('unit_price', 0):,.2f}",
                f"${item.get('total', 0):,.2f}"
            ])
        
        # Add totals
        items_data.append(['', '', 'Subtotal:', f"${invoice_data.get('amount', 0):,.2f}"])
        items_data.append(['', '', 'Tax (0%):', '$0.00'])
        items_data.append(['', '', 'Total:', f"${invoice_data.get('amount', 0):,.2f}"])
        
        items_table = Table(items_data, colWidths=[3.5*inch, 0.8*inch, 1.2*inch, 1*inch])
        items_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -4), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -4), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.HexColor('#F8F9FA')]),
            
            # Totals rows
            ('FONTNAME', (2, -3), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (2, -3), (-1, -1), 11),
            ('LINEABOVE', (2, -3), (-1, -3), 1, colors.HexColor('#2C3E50')),
            ('LINEABOVE', (2, -1), (-1, -1), 2, colors.HexColor('#2C3E50')),
            
            # General styling
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -4), 0.5, colors.grey),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.5 * inch))
        
        # Payment instructions
        elements.append(Paragraph('<b>Payment Instructions:</b>', styles['Heading2']))
        elements.append(Spacer(1, 0.1 * inch))
        
        payment_info = f"""
        Please make payment within {(datetime.strptime(invoice_data.get('due_date', '2026-03-01'), '%Y-%m-%d') - datetime.now()).days} days.<br/>
        <br/>
        <b>Bank Transfer:</b><br/>
        Bank: First National Bank<br/>
        Account Name: RevoAI Inc.<br/>
        Account Number: 1234567890<br/>
        Routing Number: 987654321<br/>
        <br/>
        <b>Online Payment:</b><br/>
        Visit: <a href="https://pay.revoai.com">pay.revoai.com</a><br/>
        Reference: INV-{invoice_data.get('invoice_id', 'N/A')}
        """
        
        elements.append(Paragraph(payment_info, styles['Normal']))
        
        # Notes (if any)
        if invoice_data.get('notes'):
            elements.append(Spacer(1, 0.3 * inch))
            elements.append(Paragraph('<b>Notes:</b>', styles['Heading2']))
            elements.append(Paragraph(invoice_data['notes'], styles['Normal']))
        
        # Footer
        elements.append(Spacer(1, 0.5 * inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            'Thank you for your business!<br/>Questions? Contact us at billing@revoai.com',
            footer_style
        ))
        
        # Build PDF
        doc.build(elements)
        
        print(f"✅ Invoice PDF generated: {output_path}")
        return str(output_path)
    
    except Exception as e:
        print(f"❌ Failed to generate PDF: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Sample invoice data
    sample_invoice = {
        'invoice_id': 12345,
        'customer_name': 'Alice Wright',
        'customer_company': 'CloudScale',
        'customer_email': 'alice@cloudscale.io',
        'amount': 75000.00,
        'due_date': '2026-03-07',
        'line_items': [
            {
                'description': 'RevoAI Enterprise Plan - Annual License',
                'quantity': 1,
                'unit_price': 60000.00,
                'total': 60000.00
            },
            {
                'description': 'Professional Implementation Services',
                'quantity': 1,
                'unit_price': 15000.00,
                'total': 15000.00
            }
        ],
        'notes': 'Payment terms: Net 30. Late payments subject to 1.5% monthly interest.'
    }
    
    pdf_path = generate_invoice_pdf(sample_invoice)
    
    if pdf_path:
        print(f"\n📄 Sample invoice created at: {pdf_path}")
    else:
        print("\n⚠️  Install reportlab to test: pip install reportlab")
