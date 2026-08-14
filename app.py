import streamlit as st
import pandas as pd
import io

from utils.pdf_parser import parse_invoice_pdf, diagnose_pdf
from utils.excel_exporter import export_to_excel
from utils.postal_code import get_postal_code
from utils.db_manager import load_product_db, save_product_db, lookup_product
from utils.config_manager import load_config, save_config
from utils.auth import is_authenticated, show_login_page, logout, get_session_info

# ─── 페이지 설정 ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="택배요청서 변환 대시보드",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── 카카오 API 키 로드 ──────────────────────────────────────────────────────
def _secret(key: str, fallback: str = "") -> str:
    """Streamlit Cloud는 st.secrets, 로컬은 config.json"""
    try:
        val = st.secrets.get(key, None)
        if val:
            return val
    except Exception:
        pass
    return load_config().get(key, fallback)

# ─── 인증 확인 ───────────────────────────────────────────────────────────────
if not is_authenticated():
    show_login_page()
    st.stop()

# ─── 로그인 세션 정보 (사이드바) ────────────────────────────────────────────
with st.sidebar:
    info = get_session_info()
    if info.get("picture"):
        st.image(info["picture"], width=48)
    st.markdown(f"**{info.get('name', '')}**")
    st.caption(info.get("email", ""))
    st.divider()
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()

# ─── 스타일 ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container { padding-top: 4.5rem; padding-bottom: 2rem; }
  .main-title { font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 2px; }
  .sub-title  { font-size: 13px; color: #6b7280; margin-bottom: 20px; }
  div[data-testid="stFileUploaderDropzone"] {
      border: 2px dashed #93c5fd;
      border-radius: 10px;
      background: #eff6ff;
  }
  .step-badge {
      display: inline-block;
      background: #2563eb;
      color: white;
      border-radius: 50%;
      width: 22px; height: 22px;
      text-align: center;
      line-height: 22px;
      font-size: 12px;
      font-weight: bold;
      margin-right: 6px;
  }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📦 택배요청서 변환 대시보드</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">인보이스 PDF를 업로드하면 출고요청서 엑셀로 자동 변환됩니다.</p>', unsafe_allow_html=True)

# ─── 세션 상태 초기화 ────────────────────────────────────────────────────────
if "parsed_data"     not in st.session_state: st.session_state.parsed_data     = None
if "last_file_name"  not in st.session_state: st.session_state.last_file_name  = ""
# API 키: 세션에 없으면 저장된 config 파일에서 불러오기
if "postal_api_key"  not in st.session_state:
    st.session_state.postal_api_key = _secret("kakao_api_key")

# ─── 탭 ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📄 인보이스 변환", "🗂 품목코드 DB 관리", "🔍 PDF 진단"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 : 인보이스 변환
# ════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── 상단: PDF 업로드 + 우편번호 API (한 줄) ──────────────────────────────
    st.markdown("**① 인보이스 PDF 업로드**")
    uploaded = st.file_uploader(
        "PDF 파일을 여기에 드래그하거나 클릭해서 선택하세요",
        type=["pdf"],
        label_visibility="collapsed",
    )

    st.divider()

    # ── PDF 자동 파싱 (업로드 시 즉시 실행) ──────────────────────────────────
    if uploaded:
        # 새 파일이 올라왔을 때만 재파싱
        if uploaded.name != st.session_state.last_file_name:
            with st.spinner(f"📄 {uploaded.name} 분석 중..."):
                try:
                    result = parse_invoice_pdf(uploaded)

                    # ── 파싱 결과 진단 (중간 상태 저장) ──────────────────────
                    st.session_state.parse_debug = {
                        "raw_products": [dict(p) for p in result.get("products", [])],
                        "contact_person": result.get("contact_person", ""),
                        "contact_no":     result.get("contact_no", ""),
                        "address":        result.get("address", ""),
                    }

                    # 품목 DB 매칭
                    db = load_product_db()
                    for item in result.get("products", []):
                        match = lookup_product(
                            db,
                            eng_name=item.get("name", ""),
                            barcode=item.get("barcode", ""),
                        )
                        item.update(match)

                    # 우편번호 자동 조회
                    if st.session_state.postal_api_key:
                        addr = result.get("address", "")
                        if addr:
                            postal_code, postal_err = get_postal_code(
                                addr, st.session_state.postal_api_key
                            )
                            result["postal_code"] = postal_code
                            if postal_err:
                                st.warning(f"⚠️ 우편번호 조회 실패: {postal_err}")
                    elif not st.session_state.postal_api_key:
                        st.info("ℹ️ 카카오 API 키가 설정되지 않아 우편번호를 자동 조회하지 않습니다.")

                    st.session_state.parsed_data    = result
                    st.session_state.last_file_name = uploaded.name

                except Exception as exc:
                    st.error(f"PDF 파싱 오류: {exc}")
                    st.session_state.parsed_data = None

    # ── 파싱 단계 진단 박스 ───────────────────────────────────────────────────
    if "parse_debug" in st.session_state and st.session_state.parse_debug:
        dbg = st.session_state.parse_debug
        raw_products = dbg.get("raw_products", [])

        with st.expander("🔎 파싱 단계 진단 (어디서 막혔는지 확인)", expanded=True):
            # 1단계: PDF 추출 결과
            st.markdown("**① PDF 직접 추출 결과 (DB 매칭 이전)**")
            c1, c2, c3 = st.columns(3)
            c1.metric("수령자", dbg.get("contact_person") or "❌ 미추출")
            c2.metric("연락처", dbg.get("contact_no") or "❌ 미추출")
            c3.metric("추출된 품목 수", f"{len(raw_products)}개")

            if raw_products:
                st.success("✅ 1단계 통과 — PDF에서 품목을 성공적으로 추출했습니다.")
                st.caption("아래는 DB 매칭 전 원시 데이터입니다.")
                st.dataframe(
                    raw_products,
                    column_order=["name", "barcode", "quantity", "unit_price"],
                    use_container_width=True,
                )
                st.info("ℹ️ 2단계 문제 — 어드민코드 변환이 안 되는 경우, '품목코드 DB 관리' 탭에서 해당 바코드를 등록하세요.")
            else:
                st.error("❌ 1단계 실패 — PDF에서 품목을 추출하지 못했습니다. '🔍 PDF 진단' 탭에서 원시 텍스트를 확인하세요.")

    # ── 결과 표시 ─────────────────────────────────────────────────────────────
    if st.session_state.parsed_data:
        data = st.session_state.parsed_data

        st.markdown("**② 추출 정보 확인 · 수정 후 다운로드**")

        # 수령자 정보 행
        inf1, inf2, inf3, inf4 = st.columns([1.5, 1.5, 3, 1.2])
        with inf1:
            recipient = st.text_input("수령자",   value=data.get("contact_person", ""), key="f_recipient")
        with inf2:
            phone     = st.text_input("연락처",   value=data.get("contact_no", ""),     key="f_phone")
        with inf3:
            address   = st.text_input("주소",     value=data.get("address", ""),        key="f_address")
        with inf4:
            postal    = st.text_input("우편번호", value=data.get("postal_code", ""),    key="f_postal")

        # 품목 테이블
        products = data.get("products", [])
        if products:
            df = pd.DataFrame(products)
            display_cols = {
                "barcode":     "바코드",
                "name":        "영문품목명",
                "admin_code":  "어드민코드",
                "korean_name": "한글품목명",
                "quantity":    "수량",
                "unit_price":  "매입가(VAT포함)",
                "matched":     "DB매칭",
            }
            for col in display_cols:
                if col not in df.columns:
                    df[col] = ""

            df_show = df[list(display_cols.keys())].rename(columns=display_cols)

            edited = st.data_editor(
                df_show,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "DB매칭":          st.column_config.CheckboxColumn("DB매칭", disabled=True, width="small"),
                    "수량":            st.column_config.NumberColumn("수량", min_value=0),
                    "매입가(VAT포함)": st.column_config.NumberColumn("매입가(VAT포함)", format="%d"),
                },
                key="product_editor",
            )

            # 비매칭 경고
            if "DB매칭" in df_show.columns:
                n_unmatched = int((df_show["DB매칭"] == False).sum())
                if n_unmatched:
                    st.warning(f"⚠️ DB 미매칭 품목 {n_unmatched}건 — 어드민코드를 직접 입력하거나 'DB 관리' 탭에서 등록하세요.")
        else:
            edited = pd.DataFrame()
            st.info("품목 정보를 추출하지 못했습니다. PDF 구조를 확인하거나 직접 입력해 주세요.")

        st.divider()

        # ── 엑셀 다운로드 버튼 (클릭 한 번으로 바로 다운로드) ─────────────────
        output_info = {
            "수령자":   st.session_state.get("f_recipient", data.get("contact_person", "")),
            "연락처":   st.session_state.get("f_phone",     data.get("contact_no", "")),
            "주소":     st.session_state.get("f_address",   data.get("address", "")),
            "우편번호": st.session_state.get("f_postal",    data.get("postal_code", "")),
            "products": edited.to_dict("records") if not edited.empty else [],
        }

        try:
            excel_bytes = export_to_excel(output_info)
            timestamp   = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 출고요청서 엑셀 다운로드",
                data=excel_bytes,
                file_name=f"출고요청서_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=False,
            )
        except Exception as exc:
            st.error(f"엑셀 생성 오류: {exc}")

    elif not uploaded:
        st.markdown(
            """
            <div style="text-align:center; padding: 60px 0; color: #9ca3af;">
                <div style="font-size:48px">📄</div>
                <div style="font-size:16px; margin-top:12px;">위에서 인보이스 PDF를 업로드하면<br>자동으로 변환됩니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 : 품목코드 DB 관리
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    title_col, count_col = st.columns([3, 1])
    with title_col:
        st.subheader("품목코드 DB 관리")
        st.caption("바코드 기준으로 **영문품목명 → 한글품목명 / 어드민코드**를 관리합니다.")
    with count_col:
        total = len(st.session_state.get("db_dataframe", load_product_db()))
        st.metric("등록 품목 수", f"{total:,} 개")

    # DB를 세션 상태에 캐시 — 매 렌더링마다 디스크 읽기 방지
    if "db_dataframe" not in st.session_state:
        st.session_state.db_dataframe = load_product_db()

    # 툴바
    tb1, tb2, tb3 = st.columns([3, 1, 1])
    with tb2:
        import_file = st.file_uploader(
            "엑셀 가져오기",
            type=["xlsx", "csv"],
            key="db_import",
            label_visibility="collapsed",
        )
        st.caption("📥 엑셀/CSV 가져오기")
        if import_file:
            # 같은 파일을 반복 처리하지 않도록 name+size 로 고유 ID 확인
            file_id = f"{import_file.name}_{import_file.size}"
            if file_id != st.session_state.get("last_import_id"):
                try:
                    new_db = (
                        pd.read_csv(import_file)
                        if import_file.name.endswith(".csv")
                        else pd.read_excel(import_file)
                    )
                    save_product_db(new_db)
                    st.session_state.db_dataframe = new_db
                    st.session_state.last_import_id = file_id
                    st.success(f"✅ {len(new_db)}건 가져오기 완료!")
                except Exception as exc:
                    st.error(f"가져오기 오류: {exc}")

    db = st.session_state.db_dataframe

    with tb3:
        if not db.empty:
            buf = io.BytesIO()
            db.to_excel(buf, index=False)
            st.download_button(
                "📤 엑셀 내보내기",
                data=buf.getvalue(),
                file_name="품목코드DB.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    st.divider()
    edited_db = st.data_editor(
        db,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "바코드":     st.column_config.TextColumn("바코드",     width="medium", help="스캔 바코드"),
            "영문품목명": st.column_config.TextColumn("영문품목명", width="large",  help="PDF에 표기된 영문명"),
            "한글품목명": st.column_config.TextColumn("한글품목명", width="large"),
            "어드민코드": st.column_config.TextColumn("어드민코드", width="medium", help="출고요청서에 입력될 코드"),
            "비고":       st.column_config.TextColumn("비고",       width="medium"),
        },
    )

    col_save, _ = st.columns([1, 4])
    with col_save:
        if st.button("💾 저장", type="primary", use_container_width=True):
            save_product_db(edited_db)
            st.success(f"✅ {len(edited_db)}건 저장 완료!")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 : PDF 진단 (파싱 실패 시 원시 텍스트 확인용)
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("🔍 PDF 원시 텍스트 진단")
    st.caption("파싱이 제대로 안 될 때, PDF에서 실제로 어떤 텍스트가 추출되는지 확인합니다.")

    diag_file = st.file_uploader(
        "진단할 PDF 업로드",
        type=["pdf"],
        key="diag_upload",
        label_visibility="collapsed",
    )
    if diag_file:
        with st.spinner("PDF 분석 중..."):
            try:
                raw = diagnose_pdf(diag_file)
                st.text_area("추출 결과 (pdfplumber 원시 출력)", raw, height=500)
            except Exception as exc:
                st.error(f"진단 오류: {exc}")
