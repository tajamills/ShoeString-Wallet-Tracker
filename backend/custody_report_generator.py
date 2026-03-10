"""
Chain of Custody PDF Report Generator
Generates professional PDF reports for auditors and government agencies.
"""
import io
import logging
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)


class CustodyReportGenerator:
    """
    Generates professional PDF reports for Chain of Custody analysis.
    Designed for sharing with auditors, tax authorities, and legal teams.
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#334155'),
            spaceBefore=20,
            spaceAfter=10,
            borderColor=colors.HexColor('#3b82f6'),
            borderWidth=0,
            borderPadding=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#475569'),
            spaceBefore=15,
            spaceAfter=8
        ))
        
        self.styles.add(ParagraphStyle(
            name='ReportBodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#334155'),
            spaceAfter=8
        ))
        
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=4
        ))
        
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#94a3b8'),
            alignment=TA_CENTER,
            spaceBefore=20
        ))
    
    def generate_report(self, custody_result: Dict[str, Any], user_info: Dict = None) -> bytes:
        """
        Generate a complete PDF report from custody analysis results.
        
        Args:
            custody_result: The result from custody_service.analyze_chain_of_custody()
            user_info: Optional user information for the report header
        
        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        
        # Title Page
        story.extend(self._create_title_page(custody_result, user_info))
        story.append(PageBreak())
        
        # Executive Summary
        story.extend(self._create_executive_summary(custody_result))
        
        # Analysis Details
        story.extend(self._create_analysis_details(custody_result))
        
        # Exchange Origins
        if custody_result.get('exchange_endpoints'):
            story.extend(self._create_exchange_origins_section(custody_result))
        
        # DEX Origins
        if custody_result.get('dex_endpoints'):
            story.extend(self._create_dex_origins_section(custody_result))
        
        # Dormant Origins
        dormant_origins = [o for o in custody_result.get('origin_points', []) 
                          if o.get('type') == 'dormant']
        if dormant_origins:
            story.extend(self._create_dormant_origins_section(dormant_origins))
        
        # Full Transaction Chain (limited)
        if custody_result.get('custody_chain'):
            story.append(PageBreak())
            story.extend(self._create_transaction_chain_section(custody_result))
        
        # Footer/Disclaimer
        story.extend(self._create_footer())
        
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_title_page(self, result: Dict, user_info: Dict = None) -> List:
        """Create the title page"""
        elements = []
        
        elements.append(Spacer(1, 1.5*inch))
        
        # Title
        elements.append(Paragraph(
            "Chain of Custody Analysis Report",
            self.styles['ReportTitle']
        ))
        
        elements.append(Spacer(1, 0.5*inch))
        
        # Horizontal line
        elements.append(HRFlowable(
            width="80%",
            thickness=2,
            color=colors.HexColor('#3b82f6'),
            spaceAfter=30,
            hAlign='CENTER'
        ))
        
        # Report metadata
        meta_data = [
            ["Report Generated:", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
            ["Analyzed Address:", self._truncate_address(result.get('analyzed_address', ''))],
            ["Blockchain:", result.get('chain', 'ethereum').upper()],
            ["Analysis Depth:", f"{result.get('settings', {}).get('max_depth', 10)} hops"],
            ["Dormancy Threshold:", f"{result.get('settings', {}).get('dormancy_days', 365)} days"],
        ]
        
        if user_info:
            if user_info.get('email'):
                meta_data.insert(0, ["Prepared For:", user_info['email']])
        
        meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#334155')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(meta_table)
        
        elements.append(Spacer(1, 1*inch))
        
        # Confidentiality notice
        elements.append(Paragraph(
            "CONFIDENTIAL - FOR AUTHORIZED USE ONLY",
            self.styles['Disclaimer']
        ))
        
        return elements
    
    def _create_executive_summary(self, result: Dict) -> List:
        """Create executive summary section"""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        summary = result.get('summary', {})
        
        # Summary statistics
        summary_text = f"""
        This report presents the chain of custody analysis for wallet address 
        <b>{self._truncate_address(result.get('analyzed_address', ''))}</b> 
        on the {result.get('chain', 'Ethereum').upper()} blockchain.
        """
        elements.append(Paragraph(summary_text, self.styles['ReportBodyText']))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Summary statistics table
        stats_data = [
            ["Metric", "Value"],
            ["Total Links Traced", str(summary.get('total_links_traced', 0))],
            ["Unique Addresses Visited", str(summary.get('unique_addresses_visited', 0))],
            ["Exchange Origins Found", str(summary.get('exchange_origins', 0))],
            ["DEX Origins Found", str(summary.get('dex_origins', 0))],
            ["Dormant Wallet Origins", str(summary.get('dormant_origins', 0))],
            ["Unknown Origins", str(summary.get('unknown_origins', 0))],
        ]
        
        if summary.get('total_value_from_exchanges', 0) > 0:
            stats_data.append([
                "Total Value from Exchanges", 
                f"{summary.get('total_value_from_exchanges', 0):.4f} ETH"
            ])
        
        if summary.get('total_value_from_dex', 0) > 0:
            stats_data.append([
                "Total Value from DEXs", 
                f"{summary.get('total_value_from_dex', 0):.4f} ETH"
            ])
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        
        elements.append(stats_table)
        
        return elements
    
    def _create_analysis_details(self, result: Dict) -> List:
        """Create analysis details section"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Analysis Parameters", self.styles['SubHeader']))
        
        settings = result.get('settings', {})
        
        params_text = f"""
        <b>Max Depth:</b> {settings.get('max_depth', 10)} hops (0 = unlimited)<br/>
        <b>Dormancy Threshold:</b> {settings.get('dormancy_days', 365)} days<br/>
        <b>Analysis Timestamp:</b> {result.get('analysis_timestamp', 'N/A')}<br/>
        """
        
        elements.append(Paragraph(params_text, self.styles['ReportBodyText']))
        
        return elements
    
    def _create_exchange_origins_section(self, result: Dict) -> List:
        """Create exchange origins section"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Exchange Origins", self.styles['SectionHeader']))
        
        elements.append(Paragraph(
            "The following centralized exchanges were identified as origin points for funds:",
            self.styles['ReportBodyText']
        ))
        
        exchange_data = [["Exchange", "Value", "Date", "Depth", "Transaction Hash"]]
        
        for ep in result.get('exchange_endpoints', [])[:20]:  # Limit to 20
            exchange_data.append([
                ep.get('exchange', 'Unknown'),
                f"{ep.get('value', 0):.6f}",
                self._format_date(ep.get('timestamp')),
                str(ep.get('depth', 0)),
                self._truncate_hash(ep.get('tx_hash', ''))
            ])
        
        if len(result.get('exchange_endpoints', [])) > 20:
            exchange_data.append(["...", f"+{len(result['exchange_endpoints']) - 20} more", "", "", ""])
        
        exchange_table = Table(exchange_data, colWidths=[1.2*inch, 1*inch, 1*inch, 0.6*inch, 2.2*inch])
        exchange_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#22c55e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0fdf4'), colors.white]),
        ]))
        
        elements.append(exchange_table)
        
        return elements
    
    def _create_dex_origins_section(self, result: Dict) -> List:
        """Create DEX origins section"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("DEX Swap Origins", self.styles['SectionHeader']))
        
        elements.append(Paragraph(
            "The following decentralized exchanges were identified as swap/conversion points:",
            self.styles['ReportBodyText']
        ))
        
        dex_data = [["DEX", "Value", "Date", "Depth", "Transaction Hash"]]
        
        for ep in result.get('dex_endpoints', [])[:20]:  # Limit to 20
            dex_data.append([
                ep.get('dex', 'Unknown'),
                f"{ep.get('value', 0):.6f}",
                self._format_date(ep.get('timestamp')),
                str(ep.get('depth', 0)),
                self._truncate_hash(ep.get('tx_hash', ''))
            ])
        
        if len(result.get('dex_endpoints', [])) > 20:
            dex_data.append(["...", f"+{len(result['dex_endpoints']) - 20} more", "", "", ""])
        
        dex_table = Table(dex_data, colWidths=[1.5*inch, 1*inch, 1*inch, 0.6*inch, 1.9*inch])
        dex_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#eff6ff'), colors.white]),
        ]))
        
        elements.append(dex_table)
        
        return elements
    
    def _create_dormant_origins_section(self, dormant_origins: List) -> List:
        """Create dormant origins section"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Dormant Wallet Origins", self.styles['SectionHeader']))
        
        elements.append(Paragraph(
            "The following addresses showed no activity beyond the dormancy threshold and are considered origin points:",
            self.styles['ReportBodyText']
        ))
        
        dormant_data = [["Address", "Last Activity", "Depth", "Reason"]]
        
        for origin in dormant_origins[:15]:
            dormant_data.append([
                self._truncate_address(origin.get('address', '')),
                self._format_date(origin.get('last_activity')),
                str(origin.get('depth', 0)),
                origin.get('reason', 'Dormant')[:30]
            ])
        
        dormant_table = Table(dormant_data, colWidths=[2*inch, 1.2*inch, 0.6*inch, 2.2*inch])
        dormant_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f97316')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fff7ed'), colors.white]),
        ]))
        
        elements.append(dormant_table)
        
        return elements
    
    def _create_transaction_chain_section(self, result: Dict) -> List:
        """Create transaction chain section"""
        elements = []
        
        elements.append(Paragraph("Transaction Chain Detail", self.styles['SectionHeader']))
        
        chain = result.get('custody_chain', [])
        total = len(chain)
        shown = min(50, total)
        
        elements.append(Paragraph(
            f"Showing {shown} of {total} traced transaction links:",
            self.styles['SmallText']
        ))
        
        chain_data = [["From", "To", "Value", "Type", "Depth"]]
        
        for link in chain[:50]:
            chain_data.append([
                self._truncate_address(link.get('from', '')),
                self._truncate_address(link.get('to', '')),
                f"{link.get('value', 0):.4f}",
                link.get('origin_type', 'transfer'),
                str(link.get('depth', 0))
            ])
        
        chain_table = Table(chain_data, colWidths=[1.4*inch, 1.4*inch, 1*inch, 1.2*inch, 0.6*inch])
        chain_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#eef2ff'), colors.white]),
        ]))
        
        elements.append(chain_table)
        
        return elements
    
    def _create_footer(self) -> List:
        """Create report footer"""
        elements = []
        
        elements.append(Spacer(1, 0.5*inch))
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor('#e2e8f0'),
            spaceAfter=10
        ))
        
        disclaimer = """
        <b>Disclaimer:</b> This report is generated by automated blockchain analysis software 
        and is provided for informational purposes only. The analysis traces on-chain transactions 
        and may not represent the complete picture of asset movements. This report should be 
        reviewed by qualified professionals before being used for tax, legal, or compliance purposes.
        The software cannot verify off-chain transactions or the identity of wallet owners.
        """
        
        elements.append(Paragraph(disclaimer, self.styles['Disclaimer']))
        
        elements.append(Spacer(1, 0.2*inch))
        
        elements.append(Paragraph(
            f"Generated by Crypto Bag Tracker | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['Disclaimer']
        ))
        
        return elements
    
    @staticmethod
    def _truncate_address(address: str, length: int = 12) -> str:
        """Truncate address for display"""
        if not address or len(address) < length * 2:
            return address or ''
        return f"{address[:length]}...{address[-8:]}"
    
    @staticmethod
    def _truncate_hash(tx_hash: str, length: int = 10) -> str:
        """Truncate transaction hash for display"""
        if not tx_hash or len(tx_hash) < length * 2:
            return tx_hash or ''
        return f"{tx_hash[:length]}...{tx_hash[-6:]}"
    
    @staticmethod
    def _format_date(timestamp: str) -> str:
        """Format timestamp for display"""
        if not timestamp:
            return 'N/A'
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', ''))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return timestamp[:10] if len(timestamp) >= 10 else timestamp


# Global instance
custody_report_generator = CustodyReportGenerator()
