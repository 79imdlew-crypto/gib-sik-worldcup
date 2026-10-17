import random
import uuid

import streamlit as st
from supabase import create_client


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="급식 반찬 월드컵",
    page_icon="🍱",
    layout="centered",
)

MENUS = [
    "제육볶음",
    "간장찜닭",
    "가자미순살튀김",
    "돈육불백",
    "미트볼데리야끼볶음",
    "수육",
    "진미채고추장볶음",
    "치즈떡닭갈비",
]

ROUND_NAMES = ["8강", "4강", "결승"]

st.title("🍱 급식 반찬 월드컵")
st.caption("8개의 반찬 중 오늘의 최애 반찬을 골라 보세요!")
st.divider()


# --------------------------------------------------
# Supabase 연결
# 기존 menu_duels 테이블만 사용합니다.
# --------------------------------------------------
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# --------------------------------------------------
# 새 월드컵 시작
# --------------------------------------------------
def start_new_game():
    shuffled_menus = MENUS.copy()
    random.shuffle(shuffled_menus)

    st.session_state.game_id = str(uuid.uuid4())
    st.session_state.round_name = "8강"
    st.session_state.round_menus = shuffled_menus
    st.session_state.match_index = 0
    st.session_state.round_winners = []
    st.session_state.champion = None
    st.session_state.locked = False
    st.session_state.lock_reason = ""


if "game_id" not in st.session_state:
    start_new_game()


# --------------------------------------------------
# 대결 결과 저장 및 다음 라운드 처리
# --------------------------------------------------
def choose_winner(winner):
    # 오류가 발생한 대결은 재선택할 수 없습니다.
    if st.session_state.locked or st.session_state.champion:
        return

    index = st.session_state.match_index
    menus = st.session_state.round_menus
    left_menu = menus[index * 2]
    right_menu = menus[index * 2 + 1]

    # 화면에서 실제로 제시한 두 후보인지 확인합니다.
    if winner not in (left_menu, right_menu):
        st.session_state.locked = True
        st.session_state.lock_reason = (
            "선택한 반찬을 확인할 수 없습니다."
        )
        return

    # 선택 전에 반드시 DB 저장 결과를 확인합니다.
    try:
        supabase = get_supabase()

        result = (
            supabase.table("menu_duels")
            .insert(
                {
                    "game_id": st.session_state.game_id,
                    "round": st.session_state.round_name,
                    "left_menu": left_menu,
                    "right_menu": right_menu,
                    "winner": winner,
                }
            )
            .execute()
        )

        # 반환된 행이 정확히 한 개이고,
        # 저장된 대결 내용이 요청한 내용과 일치해야 합니다.
        rows = result.data
        expected = {
            "game_id": st.session_state.game_id,
            "round": st.session_state.round_name,
            "left_menu": left_menu,
            "right_menu": right_menu,
            "winner": winner,
        }

        confirmed = (
            isinstance(rows, list)
            and len(rows) == 1
            and all(rows[0].get(k) == v for k, v in expected.items())
        )

        if not confirmed:
            st.session_state.locked = True
            st.session_state.lock_reason = (
                "데이터베이스 저장 결과를 확인할 수 없습니다. "
                "중복 기록을 방지하기 위해 재선택을 잠갔습니다."
            )
            return

    except Exception:
        st.session_state.locked = True
        st.session_state.lock_reason = (
            "데이터베이스 오류 또는 응답 확인 실패가 발생했습니다. "
            "기록이 이미 저장되었을 가능성도 있으므로 재선택하지 마세요. "
            "교사의 확인이 필요합니다."
        )
        return

    # 저장이 확인된 경우에만 승자를 반영합니다.
    st.session_state.round_winners.append(winner)
    st.session_state.match_index += 1

    total_matches = len(st.session_state.round_menus) // 2

    # 현재 라운드의 모든 대결이 끝났습니다.
    if st.session_state.match_index == total_matches:
        winners = st.session_state.round_winners

        if st.session_state.round_name == "결승":
            st.session_state.champion = winners[0]

        else:
            current_round_index = ROUND_NAMES.index(
                st.session_state.round_name
            )
            st.session_state.round_name = (
                ROUND_NAMES[current_round_index + 1]
            )
            st.session_state.round_menus = winners
            st.session_state.round_winners = []
            st.session_state.match_index = 0


# --------------------------------------------------
# 진행 상황
# --------------------------------------------------
round_name = st.session_state.round_name
match_index = st.session_state.match_index
round_menus = st.session_state.round_menus

if st.session_state.champion is None:
    round_counts = {"8강": 4, "4강": 2, "결승": 1}
    total_round_matches = round_counts[round_name]

    completed_matches = {
        "8강": 0,
        "4강": 4,
        "결승": 6,
    }[round_name] + match_index

    st.progress(completed_matches / 7)
    st.caption(
        f"현재 라운드: {round_name} · "
        f"{match_index + 1}/{total_round_matches}번째 대결 · "
        f"전체 {completed_matches}/7경기 완료"
    )


# --------------------------------------------------
# 잠금 상태
# --------------------------------------------------
if st.session_state.locked:
    st.error("⚠️ 대결이 잠겼습니다.")
    st.warning(st.session_state.lock_reason)
    st.info(
        "선택을 다시 제출하지 마세요. "
        "교사가 Supabase의 menu_duels 기록을 확인해야 합니다."
    )


# --------------------------------------------------
# 우승 결과
# --------------------------------------------------
elif st.session_state.champion is not None:
    st.balloons()
    st.success("🏆 오늘의 급식 최애 반찬이 결정되었습니다!")

    st.markdown(
        f"<div style='text-align:center; padding:24px 8px;'>"
        f"<div style='font-size:64px;'>🏆</div>"
        f"<div style='font-size:30px; font-weight:700;'>"
        f"{st.session_state.champion}"
        f"</div>"
        f"<div style='font-size:16px; margin-top:8px;'>"
        f"급식 반찬 월드컵 우승!"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.caption("총 7번의 선택을 완료했습니다.")

    if st.button("🔄 새 월드컵 시작", use_container_width=True):
        start_new_game()
        st.rerun()


# --------------------------------------------------
# 대결 화면
# --------------------------------------------------
else:
    left_menu = round_menus[match_index * 2]
    right_menu = round_menus[match_index * 2 + 1]

    st.subheader(f"⚔️ {round_name}")
    st.write("둘 중 오늘의 급식으로 더 좋은 반찬 하나를 골라 주세요.")

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.markdown(
            "<div style='text-align:center; font-size:48px;'>🍚</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='text-align:center; font-size:21px; "
            f"font-weight:700; min-height:64px; "
            f"display:flex; align-items:center; justify-content:center;'>"
            f"{left_menu}</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            f"👍 {left_menu}",
            key=f"left_{st.session_state.game_id}_{round_name}_{match_index}",
            use_container_width=True,
        ):
            choose_winner(left_menu)
            st.rerun()

    with col2:
        st.markdown(
            "<div style='text-align:center; font-size:48px;'>🍱</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='text-align:center; font-size:21px; "
            f"font-weight:700; min-height:64px; "
            f"display:flex; align-items:center; justify-content:center;'>"
            f"{right_menu}</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            f"👍 {right_menu}",
            key=f"right_{st.session_state.game_id}_{round_name}_{match_index}",
            use_container_width=True,
        ):
            choose_winner(right_menu)
            st.rerun()

    st.divider()
    st.caption(
        "선택 결과는 저장이 확인된 후에만 다음 대결에 반영됩니다."
    )
