from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import Dict, List, Any
import os

# Utility function to handle text safely
def safe_paragraph(text: str, style) -> Paragraph:
    """Create a Paragraph with safe text encoding."""
    if not isinstance(text, str):
        text = str(text)
    # Try to encode as latin-1; if it fails, use ASCII approximation
    try:
        text.encode('latin-1')
        return Paragraph(text, style)
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Text contains non-latin-1 chars (Cyrillic)
        # Transliterate or use placeholder
        try:
            # For Cyrillic, just pass it through — modern reportlab handles UTF-8
            return Paragraph(text, style)
        except:
            # Fallback: return text as-is wrapped in <br/>
            return Paragraph("[Non-ASCII text]", style)


# Функция для установки шрифтов если их нет
def setup_fonts():
    """Установка и регистрация шрифтов для поддержки кириллицы и моноширинного шрифта"""
    try:
        # On Windows, try to find a system font that supports Cyrillic
        import platform
        system = platform.system()
        
        font_paths = []
        if system == 'Windows':
            # Windows system fonts
            font_paths = [
                'C:\\Windows\\Fonts\\arial.ttf',
                'C:\\Windows\\Fonts\\calibri.ttf',
                'C:\\Windows\\Fonts\\times.ttf',
            ]
        else:
            # Unix/Linux fonts
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            ]
        
        # Try each font until one works
        for font_path in font_paths:
            if os.path.isfile(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('PDFFont', font_path))
                    # For bold, use the same font
                    pdfmetrics.registerFont(TTFont('PDFFont-Bold', font_path))
                    print(f"[PDF] Successfully registered font: {font_path}")
                    return 'PDFFont', 'PDFFont-Bold', None
                except Exception as e:
                    print(f"[PDF] Failed to register {font_path}: {e}")
                    continue
        
        # If no system fonts found, use fallback
        print("[PDF] No suitable fonts found, using Helvetica fallback")
        return 'Helvetica', 'Helvetica-Bold', None
        
    except Exception as e:
        print(f"[PDF] Error in font setup: {e}")
        return 'Helvetica', 'Helvetica-Bold', None

DEFAULT_FONT, BOLD_FONT, MONO_FONT = setup_fonts()

# Force UTF-8 encoding in reportlab
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

# Configure reportlab for UTF-8 support
try:
    import reportlab.rl_config as rl_config
    rl_config.canvas_basefontname = 'Times-Roman'
except:
    pass

def generate_report_pdf(
    candidate_name: str,
    task_title: str,
    submitted_code: str,
    language: str,
    test_results: Dict[str, Any],
    trust_score: float,
    code_quality_score: float,
    recommendations: List[str],
    chat_history: List[Dict[str, str]],
    email: str | None = None,
    phone: str | None = None,
    location: str | None = None,
    position: str | None = None,
) -> BytesIO:
    """
    Генерирует PDF отчет интервью с полной информацией.
    
    Args:
        candidate_name: Имя кандидата
        task_title: Название задачи
        submitted_code: Отправленный код
        language: Язык программирования
        test_results: Результаты тестов
        trust_score: Оценка честности (0-100)
        code_quality_score: Оценка качества кода
        recommendations: Рекомендации
        chat_history: История чата
    
    Returns:
        BytesIO объект с PDF файлом
    """
    
    buffer = BytesIO()
    # Use UTF-8 encoding for Cyrillic support
    try:
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm)
    except TypeError:
        # Older ReportLab versions may not support encoding parameter
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    
    # Стили
    styles = getSampleStyleSheet()

    # Логируем входящие данные
    print(f"[PDF-GEN] Generating PDF for: {candidate_name}")
    print(f"[PDF-GEN] Task: {task_title}")
    print(f"[PDF-GEN] Using fonts: DEFAULT={DEFAULT_FONT}, BOLD={BOLD_FONT}")

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0891b2'),
        spaceAfter=12,
        spaceBefore=12,
        fontName=BOLD_FONT
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        alignment=TA_LEFT,
        fontName=DEFAULT_FONT
    )
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0891b2'),
        spaceAfter=8,
        spaceBefore=0,
        fontName=BOLD_FONT,
        alignment=TA_CENTER
    )
    
    # Заголовок
    story.append(Paragraph("HireCode AI", title_style))
    story.append(Paragraph("Отчет об интервью", styles['Heading2']))
    story.append(Spacer(1, 0.5*cm))
    
    # Информация о кандидате
    story.append(Paragraph("Информация о кандидате", heading_style))
    info_data = [
           ["Имя кандидата:", candidate_name],
           ["Задача:", task_title],
           ["Язык программирования:", language],
           ["Дата завершения:", datetime.now().strftime("%d.%m.%Y %H:%M")],
    ]
    # Prefer explicit contact parameters; fall back to `_contact` inside test_results if provided
    contact_from_results = {}
    if isinstance(test_results, dict):
        contact_from_results = test_results.get('_contact', {}) or {}

    final_email = email or contact_from_results.get('email')
    final_phone = phone or contact_from_results.get('phone')
    final_location = location or contact_from_results.get('location')
    final_position = position or contact_from_results.get('position')

    if final_email:
        info_data.append(["Email:", final_email])
    if final_phone:
        info_data.append(["Телефон:", final_phone])
    if final_location:
        info_data.append(["Город/Локация:", final_location])
    if final_position:
        info_data.append(["Должность:", final_position])
    
    # Convert all strings to paragraphs with proper styling
    styled_info_data = []
    for label, value in info_data:
        styled_info_data.append([
            safe_paragraph(label, normal_style),
            safe_paragraph(str(value) if not isinstance(value, str) else value, normal_style)
        ])
    
    info_table = Table(styled_info_data, colWidths=[4*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (0, -1), BOLD_FONT),
        ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Результаты тестирования
    story.append(Paragraph("Результаты тестирования", heading_style))
    
    # Handle both judge format and admin format for test_results
    visible_tests = []  # Initialize
    if 'visible_tests' in test_results:
        # Judge format: visible_tests is a list
        visible_tests = test_results.get('visible_tests', [])
        passed_tests = sum(1 for t in visible_tests if t.get('passed', False))
        total_tests = len(visible_tests)
        hidden_passed = test_results.get('hidden_tests_passed', 0)
    else:
        # Admin format: passed_tests and total_tests are direct keys
        passed_tests = test_results.get('passed_tests', 0)
        total_tests = test_results.get('total_tests', 0)
        hidden_passed = 0
        visible_tests = []  # Explicitly set empty for admin format
    
    # Get execution time
    if 'metrics' in test_results and 'max_elapsed_ms' in test_results.get('metrics', {}):
        execution_time = test_results['metrics']['max_elapsed_ms'] / 1000.0  # Convert ms to seconds
    else:
        execution_time = test_results.get('execution_time', 'N/A')
    
    test_data = [
        [Paragraph("<b>Метрика</b>", normal_style), Paragraph("<b>Значение</b>", normal_style)],
        [Paragraph("Пройдено тестов", normal_style), Paragraph(f"{passed_tests}/{total_tests}", normal_style)],
        [Paragraph("Процент успеха", normal_style), Paragraph(f"{(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%", normal_style)],
        [Paragraph("Время выполнения", normal_style), Paragraph(f"{execution_time:.2f}с" if isinstance(execution_time, (int, float)) else execution_time, normal_style)],
        [Paragraph("Качество кода", normal_style), Paragraph(f"{code_quality_score:.1f}/10" if code_quality_score else "Н/А", normal_style)],
    ]
    if hidden_passed > 0:
        test_data.append([Paragraph("Пройдено скрытых тестов", normal_style), Paragraph(str(hidden_passed), normal_style)])
    
    test_table = Table(test_data, colWidths=[7*cm, 9*cm])
    test_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0891b2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), BOLD_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
    ]))
    story.append(test_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Detailed test results (if visible tests available)
    if visible_tests:
        story.append(Paragraph("Детальные результаты тестов", heading_style))
        test_details_data = [
            [Paragraph("<b>Тест</b>", normal_style), Paragraph("<b>Статус</b>", normal_style), Paragraph("<b>Время (мс)</b>", normal_style)]
        ]
        for i, test in enumerate(visible_tests):
            status = "✓ Пройден" if test.get("passed", False) else "✗ Не пройден"
            status_color = "#10b981" if test.get("passed", False) else "#ef4444"
            test_details_data.append([
                Paragraph(f"Тест {i+1}", normal_style),
                Paragraph(f'<font color="{status_color}">{status}</font>', normal_style),
                Paragraph(str(test.get("elapsed_ms", "N/A")), normal_style)
            ])
        
        test_details_table = Table(test_details_data, colWidths=[3*cm, 10*cm, 3*cm])
        test_details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0891b2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), BOLD_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
        ]))
        story.append(test_details_table)
        story.append(Spacer(1, 0.8*cm))
    
    # Trust score (Anti-Cheat)
    story.append(Paragraph("Оценка честности (Анти-чит)", heading_style))
    trust_color = colors.HexColor('#10b981') if trust_score >= 80 else (
        colors.HexColor('#f59e0b') if trust_score >= 50 else colors.HexColor('#ef4444')
    )
    trust_status = "✓ Легитимная работа" if trust_score >= 80 else (
        "⚠ Возможны проблемы" if trust_score >= 50 else "✗ Обнаружены нарушения"
    )

    trust_data = [
        [Paragraph("<b>Оценка честности:</b>", normal_style), Paragraph(f'<font color="#{trust_color.hexval()}">{trust_score:.1f}%</font>', normal_style)],
        [Paragraph("<b>Статус:</b>", normal_style), Paragraph(f'<font color="#{trust_color.hexval()}">{trust_status}</font>', normal_style)],
    ]
    trust_table = Table(trust_data, colWidths=[4*cm, 12*cm])
    trust_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(trust_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Submitted code
    story.append(Paragraph("Отправленное решение", heading_style))
    code_lines = submitted_code.split('\n')
    code_display = '\n'.join(code_lines[:30])  # First 30 lines
    if len(code_lines) > 30:
        code_display += '\n... (code truncated)'
    
    code_para = Paragraph(
        f"<font face='Courier' size='8'>{code_display.replace('<', '&lt;').replace('>', '&gt;')}</font>",
        ParagraphStyle(
            'Code',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Courier',
            textColor=colors.HexColor('#333333'),
            backColor=colors.HexColor('#f5f5f5'),
            spaceAfter=8,
        )
    )
    code_frame = Table([['<font face="Courier" size="8">' + code_display.replace('<', '&lt;').replace('>', '&gt;') + '</font>']], 
                       colWidths=[15*cm])
    code_frame.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Courier'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(code_frame)
    story.append(Spacer(1, 0.8*cm))
    
    # Recommendations
    story.append(Paragraph("Рекомендации", heading_style))
    if recommendations and len(recommendations) > 0:
        for i, rec in enumerate(recommendations[:10], 1):  # up to 10 recommendations
            story.append(Paragraph(f"• {rec}", normal_style))
    else:
        story.append(Paragraph("Отличное решение! Рекомендаций нет.", normal_style))
    story.append(Spacer(1, 0.8*cm))
    
    # Chat history (brief)
    story.append(Paragraph("История чата (сокращенно)", heading_style))
    if chat_history and len(chat_history) > 0:
        chat_data = [[Paragraph("<b>Интервьюер</b>", normal_style), Paragraph("<b>Вопрос/Ответ</b>", normal_style)]]
        for msg in chat_history[-6:]:  # last 6 messages
            sender = "Кандидат" if msg.get('role') == 'user' else "Интервьюер"
            content = msg.get('content', '')[:100]  # first 100 chars
            if len(msg.get('content', '')) > 100:
                content += '...'
            chat_data.append([Paragraph(sender, normal_style), Paragraph(content, normal_style)])
        
        chat_table = Table(chat_data, colWidths=[3*cm, 13*cm])
        chat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0891b2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), BOLD_FONT),
            ('FONTNAME', (1, 1), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(chat_table)
    else:
        story.append(Paragraph("История чата пуста", normal_style))
    
    story.append(Spacer(1, 1*cm))
    
    # Итоговый вывод
    story.append(Paragraph("Итоговая оценка", heading_style))
    
    # Calculate overall score with proper weighting
    # Weighting: Tests 40%, Trust 30%, Code Quality 30%
    test_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    code_quality_normalized = (code_quality_score * 10) if code_quality_score else 0
    
    overall_score = (test_score * 0.4 + trust_score * 0.3 + code_quality_normalized * 0.3)
    
    result_color = colors.HexColor('#10b981') if overall_score >= 75 else (
        colors.HexColor('#f59e0b') if overall_score >= 50 else colors.HexColor('#ef4444')
    )
    
    result_text = "Рекомендуется на следующий этап ✓" if overall_score >= 75 else (
        "Требует дополнительного рассмотрения" if overall_score >= 50 else "Не рекомендуется ✗"
    )
    
    final_data = [
        [Paragraph("<b>Итоговый результат:</b>", normal_style), Paragraph(f'<font color="#{result_color.hexval()}">{overall_score:.1f}/100</font>', normal_style)],
        [Paragraph("<b>Решение:</b>", normal_style), Paragraph(f'<font color="#{result_color.hexval()}">{result_text}</font>', normal_style)],
    ]
    final_table = Table(final_data, colWidths=[4*cm, 12*cm])
    final_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(final_table)
    
    # Подпись
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("_" * 50, normal_style))
    story.append(Paragraph(f"Отчет создан: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
    story.append(Paragraph("HireCode AI - Интеллектуальная система оценки кандидатов", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
    
    # Построение PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

print(f"[PDF] Fonts in use: DEFAULT={DEFAULT_FONT}, BOLD={BOLD_FONT}")
