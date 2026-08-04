import fitz

from app.tools.pdf_parser import extract_pdf_text


def test_extract_pdf_text(tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "姓名：张三\n技能：Python", fontname="china-s")
    doc.save(str(pdf_path))
    doc.close()

    text = extract_pdf_text(str(pdf_path))
    assert "张三" in text
    assert "Python" in text
