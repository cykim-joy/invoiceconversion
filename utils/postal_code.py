"""
postal_code.py
──────────────
카카오 주소 검색 API를 이용하여 주소로 우편번호를 조회합니다.
"""

import re
import requests

KAKAO_API_URL = "https://dapi.kakao.com/v2/local/search/address.json"


def get_postal_code(address: str, api_key: str, timeout: int = 5):
    """
    주소 문자열로 우편번호(5자리)를 조회합니다.

    Returns
    -------
    (우편번호, 오류메시지)  — 성공 시 ("12345", ""), 실패 시 ("", "오류 내용")
    """
    if not api_key:
        return "", "API 키가 설정되지 않았습니다."
    if not address:
        return "", "주소가 비어 있습니다."

    headers = {"Authorization": f"KakaoAK {api_key}"}
    query   = _simplify_address(address)
    params  = {"query": query, "size": 1}

    try:
        resp = requests.get(KAKAO_API_URL, headers=headers, params=params, timeout=timeout)

        if resp.status_code == 401:
            return "", "API 키 인증 실패 (401) — REST API 키가 맞는지, 카카오 콘솔에서 Web 플랫폼(http://localhost:8501)이 등록됐는지 확인하세요."
        if resp.status_code == 403:
            return "", "API 접근 거부 (403) — 카카오 콘솔에서 카카오 로컬 API 사용 설정이 켜져 있는지 확인하세요."
        if resp.status_code != 200:
            return "", f"API 오류 (HTTP {resp.status_code}): {resp.text[:200]}"

        documents = resp.json().get("documents", [])
        if not documents:
            return "", f"주소 검색 결과 없음 (검색어: '{query}')"

        doc  = documents[0]
        road = doc.get("road_address") or {}
        addr = doc.get("address") or {}
        code = road.get("zone_no") or addr.get("zip_code", "")

        if code:
            return code, ""
        return "", "우편번호 필드가 응답에 없습니다."

    except requests.exceptions.ConnectionError:
        return "", "네트워크 연결 오류 — 인터넷 연결을 확인하세요."
    except requests.exceptions.Timeout:
        return "", f"API 응답 시간 초과 ({timeout}초)"
    except Exception as e:
        return "", f"예외 발생: {e}"


def _simplify_address(address: str) -> str:
    """상세주소(동/호수, 건물명 등)를 제거해 검색 정확도를 높입니다."""
    address = address.split(",")[0]
    address = re.sub(r"\(.*?\)", "", address)
    address = re.sub(r"\d+동\s*\d*호?", "", address)
    return address.strip()
