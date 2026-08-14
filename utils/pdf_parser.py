"""
pdf_parser.py
─────────────
인보이스 PDF에서 필요한 정보를 추출합니다.

※ 실제 PDF 구조 (ABSORBLAB / CELIMAX 인보이스 기준)
  - 1페이지 텍스트에 Forwarder Information 섹션 존재
  - 2페이지 상품 테이블은 pdfplumber가 하나의 거대한 셀로 병합하여 추출
    → 셀 내부 텍스트를 직접 파싱해야 함

추출 대상
  - Forwarder Information : Contact Person / Contact No / Address
  - Products 테이블       : Product Name / Barcode / Unit Price(KRW) / Quantity
"""

import re
import io
import pdfplumber


# ─── 유틸 ─────────────────────────────────────────────────────────────────────

def _clean(value: str) -> str:
    """앞뒤 공백·구분자 제거 및 내부 연속 공백 정리"""
    v = str(value).strip().strip("|:").strip()
    return re.sub(r"\s+", " ", v)


# ─── Forwarder Information 추출 ───────────────────────────────────────────────

def _extract_forwarder_info(full_text: str) -> dict:
    """
    전체 텍스트에서 Forwarder Information 섹션을 잘라내고
    Contact Person / Contact No / Address를 정규식으로 추출합니다.
    """
    # ── 섹션 분리: "Forwarder Information" 이후 ~ "Expected Shipping" 이전 ──
    section_text = full_text
    start_m = re.search(r"Forwarder\s+Information", full_text, re.IGNORECASE)
    if start_m:
        start = start_m.end()
        end_m = re.search(
            r"\n\s*(?:Expected\s+Shipping|Shipping\s+Date|[\r\n]{2,})",
            full_text[start:],
            re.IGNORECASE,
        )
        end = start + end_m.start() if end_m else start + 500
        section_text = full_text[start:end]

    result = {}
    patterns = {
        "contact_person": r"Contact\s+Person\s*:?\s*([^\n]+)",
        "contact_no":     r"Contact\s+No\.?\s*:?\s*([^\n]+)",
        "address":        r"Address\s*:?\s*([^\n]+)",
    }

    for field, pattern in patterns.items():
        m = re.search(pattern, section_text, re.IGNORECASE)
        if m:
            val = _clean(m.group(1))
            # 값이 다른 필드명처럼 보이면 제외 (ex. "Address:")
            if val and not re.match(
                r"^(contact|company|shipping|note|address)\s*:?$", val, re.I
            ):
                result[field] = val

    return result


# ─── Products 테이블 추출 ─────────────────────────────────────────────────────

# 바코드: EAN-13 (13자리) 또는 유사한 8~14자리 연속 숫자
BARCODE_RE = re.compile(r"\b(\d{8,14})\b")
# HSCode 형식: 4자리.2자리.4자리 (예: 3304.99.1000)
HSCODE_RE  = re.compile(r"\b\d{4}\.\d{2}\.\d{4}\b")


def _parse_merged_cell(cell_text: str) -> list:
    """
    pdfplumber가 상품 테이블 전체를 하나의 셀로 병합했을 때 파싱합니다.

    실제 PDF 텍스트 구조 예시:
        Unit
        No. Product Name Barcode HSCode Quantity Subtotal Memo
        Price(KRW)
        CELIMAX THE REAL NONI          ← 품목명 시작 줄 (번호 없음)
        1 MOISTURE BALANCING 8809954940132 3304.99.1000 9,625.00 24 231,000.00 -
        TONER 150ML                    ← 품목명 마지막 줄 (번호 없음)
        Total Quantity: 24 EA
        Total Amount: 231,000.00
    """
    products = []
    lines = [ln.strip() for ln in cell_text.splitlines()]

    # 데이터 행: 바코드가 포함되고, 행 시작이 숫자인 줄
    data_line_indices = []
    for i, line in enumerate(lines):
        if BARCODE_RE.search(line) and re.match(r"^\d+\s", line):
            data_line_indices.append(i)

    for idx in data_line_indices:
        data_line = lines[idx]

        # ── 바코드 추출 ───────────────────────────────────────────────────────
        barcode_m = BARCODE_RE.search(data_line)
        barcode = barcode_m.group(1) if barcode_m else ""

        # ── 품목명 조합 ───────────────────────────────────────────────────────
        name_parts = []

        # 데이터 행 이전의 순수 텍스트 줄들(번호·바코드 없음) = 품목명 앞부분
        for j in range(idx - 1, max(idx - 5, -1), -1):
            prev = lines[j]
            if not prev:
                break
            if re.search(r"(Price\(KRW\)|HSCode|Product Name|No\.|Unit)", prev, re.I):
                break
            if re.search(r"(Total|Grand Total)", prev, re.I):
                break
            if BARCODE_RE.search(prev) or re.match(r"^\d+\s", prev):
                break
            name_parts.insert(0, prev)

        # 데이터 행 자체에서 바코드 앞의 부분(행번호 제거 후) = 품목명 중간
        before_barcode = data_line[: barcode_m.start()].strip() if barcode_m else ""
        middle = re.sub(r"^\d+\s+", "", before_barcode).strip()  # 행번호 제거
        if middle:
            name_parts.append(middle)

        # 데이터 행 이후의 순수 텍스트 줄들 = 품목명 뒷부분
        for j in range(idx + 1, min(idx + 5, len(lines))):
            nxt = lines[j]
            if not nxt:
                break
            if re.search(r"(Total|Grand Total)", nxt, re.I):
                break
            if BARCODE_RE.search(nxt) or re.match(r"^\d+\s", nxt):
                break
            if re.match(r"^[\d\s,\.]+$", nxt):  # 순수 숫자만 있는 줄
                break
            name_parts.append(nxt)

        full_name = " ".join(p for p in name_parts if p)

        # ── 가격 / 수량 추출 ──────────────────────────────────────────────────
        # 바코드 이후 텍스트: "3304.99.1000 9,625.00 24 231,000.00 -"
        after_barcode = data_line[barcode_m.end() :].strip() if barcode_m else ""

        # HSCode 제거 (있는 경우)
        after_barcode = HSCODE_RE.sub("", after_barcode).strip()

        # 숫자(콤마·소수점 포함) 순서대로 추출
        num_strs = re.findall(r"[\d,]+(?:\.\d+)?", after_barcode)
        nums = []
        for s in num_strs:
            try:
                nums.append(float(s.replace(",", "")))
            except ValueError:
                pass

        # 컬럼 순서: Unit Price | Quantity | Subtotal (| Memo)
        price = nums[0] if len(nums) >= 1 else 0.0
        qty   = int(nums[1]) if len(nums) >= 2 else 0

        products.append({
            "barcode":     barcode,
            "name":        full_name,
            "quantity":    qty,
            "unit_price":  price,
            "korean_name": "",
            "admin_code":  "",
            "matched":     False,
        })

    return products


def _extract_products(all_tables: list, page_texts: list) -> list:
    """
    1. pdfplumber 테이블에서 품목 추출 시도
       - 셀이 하나로 병합된 경우 → _parse_merged_cell 사용
       - 정상적인 다중 셀 테이블인 경우 → 헤더 기반 파싱
    2. 실패 시 전체 텍스트에서 직접 추출
    """
    # ── 전략 1: pdfplumber 테이블 ────────────────────────────────────────────
    for table in all_tables:
        if not table:
            continue

        # 첫 번째 데이터 행이 셀 1개이고 내부에 바코드가 있으면 → 병합 셀
        first_row = table[0] if table else []
        if (
            len(first_row) == 1
            and first_row[0]
            and BARCODE_RE.search(str(first_row[0]))
        ):
            products = _parse_merged_cell(str(first_row[0]))
            if products:
                return products

        # 정상적인 다중 셀 테이블: 헤더 탐색
        header_idx = None
        header_row = None
        for i, row in enumerate(table[:6]):
            if not row:
                continue
            row_lower = [str(c).lower().strip() if c else "" for c in row]
            if any("product" in c or "item" in c or "name" in c for c in row_lower) and \
               any("quantity" in c or "qty" in c for c in row_lower):
                header_idx = i
                header_row = row_lower
                break

        if header_idx is None:
            continue

        def find_col(*keywords):
            for kw in keywords:
                for j, h in enumerate(header_row):
                    if kw in h:
                        return j
            return None

        idx_name    = find_col("product", "item", "name")
        idx_qty     = find_col("quantity", "qty")
        idx_price   = find_col("unit price", "price")
        idx_barcode = find_col("barcode", "sku")

        products = []
        for row in table[header_idx + 1:]:
            if not row or all(not c for c in row):
                continue
            def get(idx):
                if idx is not None and idx < len(row) and row[idx]:
                    return _clean(str(row[idx]))
                return ""
            name = get(idx_name)
            if not name or re.search(r"total", name, re.I):
                continue
            barcode = get(idx_barcode)
            qty_s   = get(idx_qty)
            price_s = get(idx_price)
            try:
                qty = int(re.sub(r"[^\d]", "", qty_s)) if qty_s else 0
            except ValueError:
                qty = 0
            try:
                price = float(re.sub(r"[^\d.]", "", price_s)) if price_s else 0.0
            except ValueError:
                price = 0.0
            products.append({
                "barcode": barcode, "name": name,
                "quantity": qty, "unit_price": price,
                "korean_name": "", "admin_code": "", "matched": False,
            })
        if products:
            return products

    # ── 전략 2: 전체 텍스트에서 바코드 포함 행 파싱 ──────────────────────────
    full_text = "\n".join(page_texts)
    # 페이지 전체를 하나의 가상 병합 셀로 취급
    products = _parse_merged_cell(full_text)
    return products


# ─── 공개 API ─────────────────────────────────────────────────────────────────

def parse_invoice_pdf(file_obj) -> dict:
    """
    인보이스 PDF를 파싱하여 dict 반환.

    Returns
    -------
    {
        "contact_person": str,
        "contact_no":     str,
        "address":        str,
        "postal_code":    str,
        "products": [
            {"barcode": str, "name": str, "quantity": int, "unit_price": float,
             "korean_name": str, "admin_code": str, "matched": bool},
            ...
        ]
    }
    """
    if hasattr(file_obj, "read"):
        data = file_obj.read()
        file_obj = io.BytesIO(data)

    page_texts = []
    all_tables = []

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_texts.append(text)
            tables = page.extract_tables() or []
            all_tables.extend(tables)

    full_text = "\n".join(page_texts)

    forwarder = _extract_forwarder_info(full_text)
    products  = _extract_products(all_tables, page_texts)

    return {
        "contact_person": forwarder.get("contact_person", ""),
        "contact_no":     forwarder.get("contact_no", ""),
        "address":        forwarder.get("address", ""),
        "postal_code":    "",
        "products":       products,
    }


def diagnose_pdf(file_obj) -> str:
    """PDF 파싱 진단용 — 원시 텍스트와 테이블 구조를 반환합니다."""
    if hasattr(file_obj, "read"):
        data = file_obj.read()
        file_obj = io.BytesIO(data)

    out = []
    with pdfplumber.open(file_obj) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            out.append(f"\n{'='*60}")
            out.append(f"PAGE {page_no}")
            out.append("--- TEXT ---")
            out.append(page.extract_text() or "(no text)")
            for t_no, table in enumerate(page.extract_tables() or [], 1):
                out.append(f"\n--- TABLE {t_no} (rows={len(table)}) ---")
                for r_no, row in enumerate(table):
                    out.append(f"  row[{r_no}] cells={len(row)}: {row}")

    return "\n".join(out)
