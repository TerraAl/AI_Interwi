from datetime import datetime
from io import BytesIO
from typing import Dict, List, Any
from fpdf import FPDF
import os

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
    # Добавим путь к шрифту как аргумент (можно захардкодить внутри)
    font_path: str = "DejaVuSans.ttf" 
) -> BytesIO:
    
    print(f"[PDF-GEN] Generating PDF for: {candidate_name}")
    
    pdf = FPDF()
    pdf.add_page()
    
    # --- ИСПРАВЛЕНИЕ: Добавляем шрифт с поддержкой кириллицы ---
    FONT_REGULAR = "/app/fonts/DejaVuSans.ttf"
    FONT_BOLD = "/app//fonts/DejaVuSans-Bold.ttf"

    if os.path.exists(FONT_REGULAR):
        pdf.add_font("DejaVu", "", FONT_REGULAR, uni=True)

        if os.path.exists(FONT_BOLD):
            pdf.add_font("DejaVu", "B", FONT_BOLD, uni=True)
        else:
            pdf.add_font("DejaVu", "B", FONT_REGULAR, uni=True)

        main_font = "DejaVu"

    else:
        raise RuntimeError("Missing DejaVuSans.ttf — Unicode PDF cannot be generated.")

    # -----------------------------------------------------------

    # Используем main_font вместо "Helvetica"
    pdf.set_font(main_font, "B", 20)
    pdf.cell(0, 10, "HireCode AI", ln=True, align="C")
    
    pdf.set_font(main_font, "", 12)
    pdf.cell(0, 10, "Report", ln=True, align="C")
    pdf.ln(10)
    
    # Candidate info section
    pdf.set_font(main_font, "B", 14)
    pdf.cell(0, 10, "Candidate Information", ln=True) # Если тут будет русский текст - сработает новый шрифт
    pdf.set_font(main_font, "", 11)
    
    col_width = 40
    row_height = 8
    
    info_items = [
        ("Candidate Name:", candidate_name), # Здесь была ошибка из-за имени на русском
        ("Task:", task_title),
        ("Language:", language),
        ("Completion Date:", datetime.now().strftime("%d.%m.%Y %H:%M")),
    ]
    
    # ... (остальной код получения контактов без изменений) ...
    contact_from_results = {}
    if isinstance(test_results, dict):
        contact_from_results = test_results.get('_contact', {}) or {}
    
    if email or contact_from_results.get('email'):
        info_items.append(("Email:", email or contact_from_results.get('email')))
    if phone or contact_from_results.get('phone'):
        info_items.append(("Phone:", phone or contact_from_results.get('phone')))
    if location or contact_from_results.get('location'):
        info_items.append(("Location:", location or contact_from_results.get('location')))
    if position or contact_from_results.get('position'):
        info_items.append(("Position:", position or contact_from_results.get('position')))
    
    # Draw info table
    for label, value in info_items:
        pdf.set_font(main_font, "B", 10)
        pdf.cell(col_width, row_height, label, border=1)
        pdf.set_font(main_font, "", 10)
        # str(value) теперь безопасно выведет кириллицу
        pdf.cell(0, row_height, str(value)[:80], border=1, ln=True)
    
    pdf.ln(5)
    
    # Test Results section
    pdf.set_font(main_font, "B", 14)
    pdf.cell(0, 10, "Test Results", ln=True)
    pdf.set_font(main_font, "", 11)
    
    # ... (Логика подсчета тестов без изменений) ...
    visible_tests = []
    if 'visible_tests' in test_results:
        visible_tests = test_results.get('visible_tests', [])
        passed_tests = sum(1 for t in visible_tests if t.get('passed', False))
        total_tests = len(visible_tests)
        hidden_passed = test_results.get('hidden_tests_passed', 0)
    else:
        passed_tests = test_results.get('passed_tests', 0)
        total_tests = test_results.get('total_tests', 0)
        hidden_passed = 0
        
    if 'metrics' in test_results and 'max_elapsed_ms' in test_results.get('metrics', {}):
        execution_time = test_results['metrics']['max_elapsed_ms'] / 1000.0
    else:
        execution_time = test_results.get('execution_time', 'N/A')

    # Test results table
    test_data = [
        ("Metric", "Value"),
        ("Tests Passed", f"{passed_tests}/{total_tests}"),
        ("Success Rate", f"{(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%"),
        ("Execution Time", f"{execution_time:.2f}s" if isinstance(execution_time, (int, float)) else str(execution_time)),
        ("Code Quality", f"{code_quality_score:.1f}/10" if code_quality_score else "N/A"),
    ]
    
    if hidden_passed > 0:
        test_data.append(("Hidden Tests Passed", str(hidden_passed)))
    
    col_width_metric = 50
    col_width_value = 130
    
    for i, (metric, value) in enumerate(test_data):
        pdf.set_font(main_font, "B" if i == 0 else "", 10)
        pdf.cell(col_width_metric, row_height, metric, border=1)
        pdf.cell(col_width_value, row_height, str(value), border=1, ln=True)
    
    pdf.ln(5)
    
    # Trust Score section
    pdf.set_font(main_font, "B", 14)
    pdf.cell(0, 10, "Anti-Cheat Score", ln=True)
    pdf.set_font(main_font, "", 11)
    
    trust_status = "PASS" if trust_score >= 80 else ("WARNING" if trust_score >= 50 else "FAIL")
    
    pdf.set_font(main_font, "B", 10)
    pdf.cell(50, row_height, "Trust Score:", border=1)
    pdf.cell(130, row_height, f"{trust_score:.1f}%", border=1, ln=True)
    pdf.cell(50, row_height, "Status:", border=1)
    pdf.cell(130, row_height, trust_status, border=1, ln=True)
    
    pdf.ln(5)
    
    # Recommendations section
    pdf.set_font(main_font, "B", 14)
    pdf.cell(0, 10, "Recommendations", ln=True)
    pdf.set_font(main_font, "", 11)
    
    if recommendations and len(recommendations) > 0:
        for rec in recommendations[:5]:
            # Важно: Рекомендации часто на русском, здесь шрифт критичен
            pdf.multi_cell(0, 6, f"- {rec[:70]}")
    else:
        pdf.cell(0, 6, "Excellent solution! No recommendations.", ln=True)
    
    pdf.ln(5)
    
    # Final score
    pdf.set_font(main_font, "B", 14)
    pdf.cell(0, 10, "Final Score", ln=True)
    pdf.set_font(main_font, "", 11)
    
    test_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    code_quality_normalized = (code_quality_score * 10) if code_quality_score else 0
    overall_score = (test_score * 0.4 + trust_score * 0.3 + code_quality_normalized * 0.3)
    
    result_text = "RECOMMENDED" if overall_score >= 75 else ("MAYBE" if overall_score >= 50 else "NOT RECOMMENDED")
    
    pdf.set_font(main_font, "B", 10)
    pdf.cell(50, row_height, "Overall Score:", border=1)
    pdf.cell(130, row_height, f"{overall_score:.1f}/100", border=1, ln=True)
    pdf.cell(50, row_height, "Decision:", border=1)
    pdf.cell(130, row_height, result_text, border=1, ln=True)
    
    # Footer
    pdf.ln(10)
    pdf.set_font(main_font, "", 8)
    pdf.cell(0, 5, f"Report created: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", align="C", ln=True)
    pdf.cell(0, 5, "HireCode AI - Intelligent Candidate Evaluation System", align="C", ln=True)
    
    pdf_output = pdf.output()
    buffer = BytesIO(pdf_output)
    buffer.seek(0)
    
    print(f"[PDF-GEN] PDF generated successfully, size: {len(pdf_output)} bytes")
    return buffer