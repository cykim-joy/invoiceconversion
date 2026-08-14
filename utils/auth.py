"""
utils/auth.py
Google OAuth 2.0 인증 모듈
- celimax.co.kr 계정만 허용
- 로그인 세션 10시간 유지
- requests_oauthlib 직접 사용 (PKCE 비활성화)
"""

import os
import time
import requests
import streamlit as st
from requests_oauthlib import OAuth2Session

# ── 상수 ────────────────────────────────────────────────────────────────────────
ALLOWED_DOMAIN   = "celimax.co.kr"
SESSION_DURATION = 10 * 3600          # 10시간 (초)

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL         = "https://oauth2.googleapis.com/token"
USERINFO_URL      = "https://www.googleapis.com/oauth2/v2/userinfo"


def _clear_session():
    for key in ["user_email", "user_name", "user_picture", "auth_time", "oauth_state", "auth_error"]:
        st.session_state.pop(key, None)


# ── 공개 API ────────────────────────────────────────────────────────────────────
def is_authenticated() -> bool:
    if "user_email" not in st.session_state or "auth_time" not in st.session_state:
        return False
    if time.time() - st.session_state["auth_time"] > SESSION_DURATION:
        _clear_session()
        return False
    return True


def logout():
    _clear_session()
    st.rerun()


def get_session_info() -> dict:
    if not is_authenticated():
        return {}
    elapsed   = time.time() - st.session_state["auth_time"]
    remaining = SESSION_DURATION - elapsed
    return {
        "email":             st.session_state.get("user_email", ""),
        "name":              st.session_state.get("user_name", ""),
        "picture":           st.session_state.get("user_picture", ""),
        "remaining_hours":   int(remaining // 3600),
        "remaining_minutes": int((remaining % 3600) // 60),
    }


def handle_oauth_callback(client_id: str, client_secret: str, redirect_uri: str) -> bool:
    """Google OAuth 콜백 처리 (PKCE 없이 code만으로 토큰 교환)"""
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    code = st.query_params.get("code")
    if not code:
        return False

    try:
        # requests_oauthlib 직접 사용 → PKCE 없이 code exchange
        oauth = OAuth2Session(client_id=client_id, redirect_uri=redirect_uri, scope=SCOPES)
        token = oauth.fetch_token(
            TOKEN_URL,
            code=code,
            client_secret=client_secret,
            include_client_id=True,
        )

        access_token = token.get("access_token", "")
        resp = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        info  = resp.json()
        email = info.get("email", "").lower()

        if not email.endswith(f"@{ALLOWED_DOMAIN}"):
            st.session_state["auth_error"] = (
                f"@{ALLOWED_DOMAIN} 계정만 접속할 수 있습니다.\n현재 계정: {email}"
            )
            st.query_params.clear()
            return False

        st.session_state["user_email"]   = email
        st.session_state["user_name"]    = info.get("name", email.split("@")[0])
        st.session_state["user_picture"] = info.get("picture", "")
        st.session_state["auth_time"]    = time.time()
        st.session_state.pop("auth_error", None)
        st.query_params.clear()
        return True

    except Exception as exc:
        st.session_state["auth_error"] = f"로그인 처리 중 오류: {exc}"
        st.query_params.clear()
        return False


def show_login_page(client_id: str, client_secret: str, redirect_uri: str):
    """로그인 페이지 렌더링"""

    if not client_id or not client_secret:
        st.error("⚠️ Google OAuth 설정이 필요합니다. config.json에 클라이언트 정보를 입력하세요.")
        return

    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    # requests_oauthlib으로 인증 URL 생성 (PKCE 없음)
    oauth = OAuth2Session(client_id=client_id, redirect_uri=redirect_uri, scope=SCOPES)
    auth_url, state = oauth.authorization_url(
        AUTHORIZATION_URL,
        access_type="offline",
        hd=ALLOWED_DOMAIN,
        prompt="select_account",
    )
    st.session_state["oauth_state"] = state

    error_msg = st.session_state.pop("auth_error", None)

    # ── 스타일 ───────────────────────────────────────────────────────────────────
    st.markdown("""
<style>
  header[data-testid="stHeader"], footer, #MainMenu { display: none !important; }
  .stApp { background: #f0f4ff !important; }
  .block-container { padding-top: 8vh !important; max-width: 580px !important; }

  /* 카드 섹션 사이 틈 제거 */
  [data-testid="stVerticalBlock"] { gap: 0 !important; }
  [data-testid="stVerticalBlock"] > div { margin-bottom: 0 !important; }

  /* Google 스타일 로그인 버튼 */
  [data-testid="stLinkButton"] { padding: 0 40px !important; }
  [data-testid="stLinkButton"] a {
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      width: 100% !important;
      background: white !important;
      color: #3c4043 !important;
      border: 1px solid #dadce0 !important;
      border-top: none !important;
      border-bottom: none !important;
      border-radius: 0 !important;
      padding: 14px 20px !important;
      font-size: 15px !important;
      font-weight: 500 !important;
      text-decoration: none !important;
      transition: background 0.15s !important;
  }
  [data-testid="stLinkButton"] a:hover {
      background: #f1f5ff !important;
      text-decoration: none !important;
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

    # ── 오류 메시지 ───────────────────────────────────────────────────────────────
    if error_msg:
        st.markdown(
            "<div style='background:#fef2f2;border-left:4px solid #f87171;"
            "padding:10px 40px;font-size:13px;color:#dc2626;'>"
            f"❌ {error_msg.replace(chr(10), '<br>')}</div>",
            unsafe_allow_html=True,
        )

    # ── 로그인 버튼 ───────────────────────────────────────────────────────────────
    st.link_button(
        "🔑  Google 계정으로 로그인",
        auth_url,
        use_container_width=True,
    )

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
        "<div style='margin-top:10px;font-size:11px;color:#9ca3af;'>"
        "로그인 후 10시간 동안 세션이 유지됩니다.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
