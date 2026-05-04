from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime


class ReportGenerator:
    """Generates PDF monthly reports for AWS usage and costs"""

    def generate_monthly_report(self, user_data, aws_data):
        """
        Generate a complete monthly PDF report.
        user_data: dict with user info
        aws_data: dict with AWS fetched data
        Returns: BytesIO object containing PDF bytes
        """
        buffer = BytesIO()

        # PDF document setup
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Styles
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=6,
            alignment=TA_CENTER
        )

        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#666666'),
            spaceAfter=20,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1a1a2e'),
            spaceBefore=15,
            spaceAfter=8,
            borderPad=4
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            spaceAfter=4
        )

        # Content list
        content = []

        # ── Header ──
        content.append(Paragraph("AWS Monitor Bot", title_style))
        content.append(Paragraph(f"Monthly Report - {datetime.now().strftime('%B %Y')}", subtitle_style))
        content.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a1a2e')))
        content.append(Spacer(1, 15))

        # ── Account Info ──
        content.append(Paragraph("Account Information", heading_style))

        account_data = [
            ['Field', 'Value'],
            ['Account Name', aws_data.get('account_name', 'N/A')],
            ['Region', aws_data.get('region', 'N/A')],
            ['Report Generated', datetime.now().strftime('%d %B %Y, %H:%M IST')],
            ['User', user_data.get('first_name', 'N/A')],
        ]

        account_table = Table(account_data, colWidths=[2.5*inch, 4*inch])
        account_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        content.append(account_table)
        content.append(Spacer(1, 15))

        # ── Cost Summary ──
        content.append(Paragraph("Cost Summary", heading_style))

        today_cost = aws_data.get('today_cost', 0) or 0
        month_cost = aws_data.get('month_cost', 0) or 0
        this_week = aws_data.get('this_week_cost', 0) or 0
        last_week = aws_data.get('last_week_cost', 0) or 0

        cost_data = [
            ['Period', 'Amount (USD)'],
            ['Today', f'${today_cost:.2f}'],
            ['This Month', f'${month_cost:.2f}'],
            ['This Week', f'${this_week:.2f}'],
            ['Last Week', f'${last_week:.2f}'],
        ]

        cost_table = Table(cost_data, colWidths=[2.5*inch, 4*inch])
        cost_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        content.append(cost_table)
        content.append(Spacer(1, 15))

        # ── EC2 Summary ──
        content.append(Paragraph("EC2 Instances", heading_style))

        instances = aws_data.get('instances', [])
        if instances:
            ec2_data = [['Instance Name', 'Type', 'CPU Usage']]
            for inst in instances[:10]:
                ec2_data.append([
                    inst.get('name', 'N/A'),
                    inst.get('type', 'N/A'),
                    f"{inst.get('cpu', 0)}%"
                ])

            ec2_table = Table(ec2_data, colWidths=[2.5*inch, 2*inch, 2*inch])
            ec2_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            content.append(ec2_table)
        else:
            content.append(Paragraph("No running EC2 instances", normal_style))

        content.append(Spacer(1, 15))

        # ── RDS Summary ──
        content.append(Paragraph("RDS Databases", heading_style))

        rds_instances = aws_data.get('rds_instances', [])
        if rds_instances:
            rds_data = [['Database ID', 'Engine', 'Status', 'Storage']]
            for db in rds_instances[:10]:
                rds_data.append([
                    db.get('id', 'N/A'),
                    db.get('engine', 'N/A'),
                    db.get('status', 'N/A'),
                    f"{db.get('storage', 0)} GB"
                ])

            rds_table = Table(rds_data, colWidths=[2*inch, 1.8*inch, 1.5*inch, 1.2*inch])
            rds_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6f42c1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            content.append(rds_table)
        else:
            content.append(Paragraph("No RDS instances found", normal_style))

        content.append(Spacer(1, 15))

        # ── S3 Summary ──
        content.append(Paragraph("S3 Storage", heading_style))

        buckets = aws_data.get('s3_buckets', [])
        if buckets:
            s3_data = [['Bucket Name', 'Size (GB)', 'Files', 'Created']]
            for bucket in buckets[:10]:
                s3_data.append([
                    bucket.get('name', 'N/A'),
                    str(bucket.get('size_gb', 0)),
                    f"{bucket.get('object_count', 0):,}",
                    bucket.get('created', 'N/A')
                ])

            s3_table = Table(s3_data, colWidths=[2.5*inch, 1.2*inch, 1.2*inch, 1.6*inch])
            s3_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fd7e14')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            content.append(s3_table)
        else:
            content.append(Paragraph("No S3 buckets found", normal_style))

        content.append(Spacer(1, 20))

        # ── Footer ──
        content.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dee2e6')))
        content.append(Spacer(1, 8))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER
        )
        content.append(Paragraph(
            f"Generated by AWS Monitor Bot | {datetime.now().strftime('%d %B %Y')}",
            footer_style
        ))

        # Build and return the PDF
        doc.build(content)
        buffer.seek(0)
        return buffer


# Test
if __name__ == '__main__':
    generator = ReportGenerator()

    # Test data
    user_data = {'first_name': 'Sourabh'}
    aws_data = {
        'account_name': 'Production',
        'region': 'us-east-1',
        'today_cost': 0.50,
        'month_cost': 12.45,
        'this_week_cost': 3.20,
        'last_week_cost': 2.80,
        'instances': [
            {'name': 'aws-monitor-bot', 'type': 't3.micro', 'cpu': 0.5},
            {'name': 'monitor-bot-2', 'type': 't3.micro', 'cpu': 1.2}
        ],
        'rds_instances': [
            {'id': 'test-db', 'engine': 'mysql 8.4', 'status': 'available', 'storage': 20}
        ],
        's3_buckets': [
            {'name': 'my-test-bucket', 'size_gb': 0.5, 'object_count': 10, 'created': '01-04-2026'}
        ]
    }

    pdf = generator.generate_monthly_report(user_data, aws_data)

    with open('test_report.pdf', 'wb') as f:
        f.write(pdf.read())

    print("PDF generated: test_report.pdf")
