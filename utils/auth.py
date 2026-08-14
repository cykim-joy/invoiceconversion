"""
utils/auth.py
Streamlit 내장 OAuth 인증 모듈 (st.login 사용)
- celimax.co.kr 계정만 허용
"""
import streamlit as st

ALLOWED_DOMAIN = "celimax.co.kr"


def is_authenticated() -> bool:
    """현재 사용자가 인증되어 있고 허용된 도메인인지 확인"""
    try:
        if not st.user.is_logged_in:
            return False
        email = (st.user.email or "").lower()
        return email.endswith(f"@{ALLOWED_DOMAIN}")
    except Exception:
        return False


def logout():
    st.logout()


def get_session_info() -> dict:
    if not is_authenticated():
        return {}
    email   = st.user.email or ""
    name    = getattr(st.user, "name", None) or email.split("@")[0]
    picture = getattr(st.user, "picture", "") or ""
    return {"email": email, "name": name, "picture": picture}


def show_login_page():
    """로그인 페이지 렌더링"""

    # 로그인은 됐지만 허용되지 않은 도메인
    try:
        if st.user.is_logged_in:
            email = st.user.email or ""
            st.markdown(
                f"<div style='background:#fef2f2;border-left:4px solid #f87171;"
                f"padding:12px 20px;font-size:13px;color:#dc2626;border-radius:4px;"
                f"margin-bottom:16px;'>"
                f"❌ @{ALLOWED_DOMAIN} 계정만 접속할 수 있습니다.<br>현재 계정: {email}</div>",
                unsafe_allow_html=True,
            )
            if st.button("🔄 다른 계정으로 로그인", use_container_width=True):
                st.logout()
            st.stop()
    except Exception:
        pass

    # ── 스타일 ───────────────────────────────────────────────────────────────────
    st.markdown("""
<style>
  header[data-testid="stHeader"], footer, #MainMenu { display: none !important; }
  .stApp { background: #f0f4ff !important; }
  .block-container { padding-top: 8vh !important; max-width: 580px !important; }
  [data-testid="stVerticalBlock"] { gap: 0 !important; }
  [data-testid="stVerticalBlock"] > div { margin-bottom: 0 !important; }
  [data-testid="stBaseButton-secondary"] {
      background: white !important;
      color: #3c4043 !important;
      border: 1px solid #dadce0 !important;
      border-top: none !important;
      border-bottom: none !important;
      border-radius: 0 !important;
      padding: 14px 20px !important;
      font-size: 15px !important;
      font-weight: 500 !important;
  }
  [data-testid="stBaseButton-secondary"]:hover {
      background: #f1f5ff !important;
  }
</style>
""", unsafe_allow_html=True)

    # ── 카드 상단 ─────────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='"
        "background:white;border-radius:20px 20px 0 0;"
        "padding:44px 40px 28px;text-align:center;"
        "border:1px solid #e5e7eb;border-bottom:none;"
        "'>"
        "<div style='font-size:48px;margin-bottom:10px;'>📦</div>"
        "<div style='font-size:24px;font-weight:700;color:#111827;margin-bottom:6px;white-space:nowrap;'>"
        "택배요청서 변환 대시보드</div>"
        "<div style='font-size:13px;color:#6b7280;line-height:1.7;margin-bottom:4px;'>"
        "Celimax 인보이스 자동 변환 시스템<br>"
        "업무용 Google 계정으로 로그인하세요.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── 로그인 버튼 ───────────────────────────────────────────────────────────────
    if st.button("🔑  Google 계정으로 로그인", use_container_width=True, key="google_login_btn"):
        st.login("google")

    # ── 카드 하단 ─────────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='"
        "background:white;border-radius:0 0 20px 20px;"
        "padding:20px 40px 28px;text-align:center;"
        "border:1px solid #e5e7eb;border-top:none;"
        "box-shadow:0 8px 24px rgba(37,99,235,0.09);"
        "'>"
        "<span style='"
        "display:inline-flex;align-items:center;gap:6px;"
        "padding:7px 16px;background:#eff6ff;"
        "border-radius:20px;font-size:12px;color:#2563eb;font-weight:500;"
        "'>🔒 @celimax.co.kr 계정만 접속 가능</span>"
        "</div>",
        unsafe_allow_html=True,
    )
