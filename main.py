# -*- coding: utf-8 -*-
import random
import uuid

import plotly.graph_objects as go
import streamlit as st
from supabase import create_client


st.set_page_config(
    page_title="급식 반찬 월드컵",
    page_icon="🍱",
    layout="wide",
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
PAGE_SIZE = 1000


def get_supabase():
    """Secrets에 저장된 접속 정보로 Supabase에 연결한다."""
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def start_game():
    """새 월드컵을 무작위 순서로 시작한다."""
    candidates = MENUS.copy()
    random.shuffle(candidates)

    st.session_state.game_id = str(uuid.uuid4())
    st.session_state.round_index = 0
    st.session_state.matches = [
        (candidates[i], candidates[i + 1])
        for i in range(0, len(candidates), 2)
    ]
    st.session_state.match_index = 0
    st.session_state.round_winners = []
    st.session_state.champion = None
    st.session_state.selection_locked = False
    st.session_state.save_error = None


def choose_menu(winner):
    """선택을 DB에 저장하고 저장 응답을 검증한 뒤에만 진행한다."""
    if st.session_state.selection_locked:
        return

    left_menu, right_menu = st.session_state.matches[
        st.session_state.match_index
    ]

    if winner not in (left_menu, right_menu) or left_menu == right_menu:
        st.session_state.selection_locked = True
        st.session_state.save_error = (
            "선택 내용을 확인할 수 없습니다. 관리자 확인이 필요합니다."
        )
        return

    round_name = ROUND_NAMES[st.session_state.round_index]

    # 요청이 중복으로 실행되지 않도록 저장 전에 잠근다.
    st.session_state.selection_locked = True

    try:
        client = get_supabase()
        result = (
            client.table("menu_duels")
            .insert(
                {
                    "game_id": st.session_state.game_id,
                    "round": round_name,
                    "left_menu": left_menu,
                    "right_menu": right_menu,
                    "winner": winner,
                }
            )
            .execute()
        )

        saved_rows = result.data
        if not isinstance(saved_rows, list) or len(saved_rows) != 1:
            raise RuntimeError("저장된 행을 확인할 수 없습니다.")

        saved = saved_rows[0]
        expected = {
            "game_id": st.session_state.game_id,
            "round": round_name,
            "left_menu": left_menu,
            "right_menu": right_menu,
            "winner": winner,
        }

        if any(saved.get(key) != value for key, value in expected.items()):
            raise RuntimeError("저장된 내용이 선택 내용과 일치하지 않습니다.")

    except Exception:
        st.session_state.save_error = (
            "대결 결과를 안전하게 확인하지 못했습니다. "
            "중복 저장 방지를 위해 선택을 잠갔습니다. "
            "관리자가 Supabase의 menu_duels 저장 결과를 확인해야 합니다. "
            "확인 전에는 새 판을 시작하지 마세요."
        )
        return

    # 저장이 확인된 경우에만 다음 경기로 넘어간다.
    st.session_state.round_winners.append(winner)

    if st.session_state.match_index + 1 < len(st.session_state.matches):
        st.session_state.match_index += 1
        st.session_state.selection_locked = False
        return

    winners = st.session_state.round_winners

    if round_name == "결승":
        st.session_state.champion = winners[0]
        st.session_state.selection_locked = False
        return

    st.session_state.round_index += 1
    st.session_state.matches = [
        (winners[i], winners[i + 1])
        for i in range(0, len(winners), 2)
    ]
    st.session_state.match_index = 0
    st.session_state.round_winners = []
    st.session_state.selection_locked = False


def fetch_all_duels():
    """menu_duels의 여섯 열을 페이지 단위로 모두 조회한다."""
    client = get_supabase()
    rows = []
    offset = 0

    while True:
        response = (
            client.table("menu_duels")
            .select("id,game_id,round,left_menu,right_menu,winner")
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )

        page = response.data
        if not isinstance(page, list):
            raise RuntimeError("조회 결과 형식이 올바르지 않습니다.")

        rows.extend(page)

        if len(page) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return rows


def load_analytics():
    """조회 성공과 실패를 구분해 분석 상태를 보관한다."""
    try:
        rows = fetch_all_duels()
        st.session_state.analytics_rows = rows
        st.session_state.analytics_status = "ok"
        st.session_state.analytics_error = None
    except Exception:
        st.session_state.analytics_status = "error"
        st.session_state.analytics_error = (
            "대결 기록을 불러오지 못했습니다. "
            "인터넷 연결, Supabase 접속 정보, 테이블 조회 권한을 확인한 뒤 "
            "다시 불러와 주세요."
        )


def render_analytics():
    """전체 대결 기록을 집계하고 표와 가로 막대그래프로 표시한다."""
    st.title("📊 학급 전체 대결 기록 분석")
    st.write(
        "전체 월드컵의 대결 기록을 반찬별로 집계합니다. "
        "진행 중인 판에서 저장된 대결도 포함됩니다."
    )

    refresh = st.button(
        "🔄 결과 다시 불러오기",
        use_container_width=False,
    )

    if (
        refresh
        or "analytics_status" not in st.session_state
    ):
        load_analytics()

    status = st.session_state.get("analytics_status")

    if status == "error":
        st.error(st.session_state.analytics_error)
        st.info(
            "조회에 실패한 상태입니다. 기록이 없는 상태와 다릅니다. "
            "접속 설정과 SELECT 권한을 확인한 뒤 다시 불러와 주세요."
        )
        return

    if status != "ok":
        st.info("대결 기록을 불러와 주세요.")
        return

    rows = st.session_state.analytics_rows

    # 모든 후보를 초기화해 기록이 없는 반찬도 결과에 표시한다.
    stats = {
        menu: {
            "menu": menu,
            "duels": 0,
            "wins": 0,
            "championships": 0,
        }
        for menu in MENUS
    }

    game_ids = set()

    for row in rows:
        game_id = row.get("game_id")
        if game_id is not None:
            game_ids.add(game_id)

        left_menu = row.get("left_menu")
        right_menu = row.get("right_menu")
        winner = row.get("winner")
        round_name = row.get("round")

        # 대결 수는 왼쪽과 오른쪽 등장 횟수를 모두 센다.
        if left_menu in stats:
            stats[left_menu]["duels"] += 1

        if right_menu in stats:
            stats[right_menu]["duels"] += 1

        if winner in stats:
            stats[winner]["wins"] += 1

            if round_name == "결승":
                stats[winner]["championships"] += 1

    # 기록 수와 판 수는 서로 다른 지표다.
    record_count = len(rows)
    game_count = len(game_ids)

    metric1, metric2 = st.columns(2)
    metric1.metric("집계한 대결 기록 수", f"{record_count:,}건")
    metric2.metric("고유 판 수", f"{game_count:,}판")

    st.caption(
        "대결 기록 수는 참여 인원수가 아닙니다. "
        "한 판에서 저장된 각 대결이 1건이며, 진행 중인 판의 기록도 "
        "집계에 포함됩니다."
    )

    if record_count == 0:
        st.info(
            "아직 저장된 대결 기록이 없습니다. "
            "월드컵에서 반찬을 선택하면 기록이 쌓이고 분석할 수 있습니다."
        )

    # 승률을 계산하고 내림차순으로 정렬한다.
    results = []
    for menu in MENUS:
        item = stats[menu]
        duels = item["duels"]
        wins = item["wins"]

        rate = (wins / duels * 100) if duels > 0 else None

        results.append(
            {
                "반찬": menu,
                "대결 수": duels,
                "승리 수": wins,
                "승률": rate,
                "우승 횟수": item["championships"],
            }
        )

    results.sort(
        key=lambda item: (
            item["승률"] is None,
            -(item["승률"] or 0),
            -item["승리 수"],
            item["반찬"],
        )
    )

    st.subheader("반찬별 성적표")

    display_rows = []
    for item in results:
        display_rows.append(
            {
                "반찬": item["반찬"],
                "대결 수": item["대결 수"],
                "승리 수": item["승리 수"],
                "승률": (
                    f"{item['승률']:.1f}%"
                    if item["승률"] is not None
                    else "아직 알 수 없음"
                ),
                "우승 횟수": item["우승 횟수"],
            }
        )

    st.dataframe(
        display_rows,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "승률은 승리 수 ÷ 대결 수 × 100으로 계산합니다. "
        "대결 기록이 없는 후보는 승률을 0%로 간주하지 않고 "
        "'아직 알 수 없음'으로 표시합니다."
    )

    st.subheader("반찬별 승률 비교")

    chart_rows = [
        item for item in results
        if item["승률"] is not None
    ]

    if chart_rows:
        # 위에서부터 승률이 높은 순으로 표시한다.
        chart_rows = list(reversed(chart_rows))

        fig = go.Figure(
            go.Bar(
                x=[item["승률"] for item in chart_rows],
                y=[item["반찬"] for item in chart_rows],
                orientation="h",
                text=[f"{item['승률']:.1f}%" for item in chart_rows],
                textposition="auto",
                marker_color="#4C9F70",
                hovertemplate=(
                    "%{y}<br>승률: %{x:.1f}%<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            xaxis_title="승률 (%)",
            yaxis_title="반찬",
            xaxis=dict(range=[0, 100], ticksuffix="%"),
            yaxis=dict(autorange=True),
            height=max(350, len(chart_rows) * 44),
            margin=dict(l=20, r=30, t=20, b=45),
        )

        st.plotly_chart(fig, use_container_width=True)

        if len(chart_rows) < len(MENUS):
            st.caption(
                "대결 기록이 없는 반찬은 승률을 계산할 수 없어 "
                "그래프에서 제외했습니다. 성적표에는 모든 후보가 표시됩니다."
            )
    else:
        st.info(
            "승률 그래프를 그릴 수 있는 대결 기록이 아직 없습니다."
        )


# 최초 상태 설정
if "game_id" not in st.session_state:
    start_game()

# 분석은 경기 진행 여부와 독립적으로 열 수 있다.
page = st.radio(
    "화면 선택",
    ["월드컵", "학급 기록 분석"],
    horizontal=True,
    label_visibility="collapsed",
)

if page == "학급 기록 분석":
    render_analytics()
    st.stop()


# 아래부터 월드컵 화면
st.title("🍱 급식 반찬 월드컵")
st.caption("오늘 가장 먹고 싶은 반찬을 골라 보세요!")
st.divider()

if st.session_state.save_error:
    st.error(st.session_state.save_error)
    st.info(
        "저장 결과를 확인하기 전에는 재선택하거나 새 판을 시작하지 마세요. "
        "위의 화면 선택 메뉴에서 학급 기록 분석을 열어 기록을 조회할 수 있습니다."
    )
    st.stop()

if st.session_state.champion is not None:
    st.balloons()
    st.subheader("🏆 최종 우승!")
    st.markdown(
        f"<div style='text-align:center; padding:28px 12px;'>"
        f"<div style='font-size:64px;'>🍽️</div>"
        f"<div style='font-size:32px; font-weight:700;'>"
        f"{st.session_state.champion}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.success("총 7번의 선택으로 월드컵이 끝났습니다.")

    if st.button("🔄 다시 시작하기", use_container_width=True):
        start_game()
        st.rerun()

    st.info(
        "학급 전체 기록은 상단의 '학급 기록 분석' 화면에서 확인할 수 있습니다."
    )
    st.stop()

round_name = ROUND_NAMES[st.session_state.round_index]
match_number = st.session_state.match_index + 1
total_matches = len(st.session_state.matches)

left_menu, right_menu = st.session_state.matches[
    st.session_state.match_index
]

completed = (
    sum([4, 2, 1][:st.session_state.round_index])
    + st.session_state.match_index
)

st.subheader(f"{round_name} · {match_number}/{total_matches} 경기")
st.progress(completed / 7)
st.caption(f"전체 진행: {completed}/7 경기 완료")
st.write("**둘 중 하나만 선택해 주세요!**")

left_col, right_col = st.columns(2, gap="medium")

with left_col:
    st.markdown(
        "<div style='text-align:center; font-size:42px;'>🍚</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='text-align:center; font-size:20px; "
        f"font-weight:700; min-height:64px; padding:8px;'>"
        f"{left_menu}</div>",
        unsafe_allow_html=True,
    )
    left_clicked = st.button(
        f"👍 {left_menu}",
        key=(
            f"left_{st.session_state.game_id}_"
            f"{st.session_state.round_index}_{match_number}"
        ),
        use_container_width=True,
        disabled=st.session_state.selection_locked,
    )

with right_col:
    st.markdown(
        "<div style='text-align:center; font-size:42px;'>🍱</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='text-align:center; font-size:20px; "
        f"font-weight:700; min-height:64px; padding:8px;'>"
        f"{right_menu}</div>",
        unsafe_allow_html=True,
    )
    right_clicked = st.button(
        f"👍 {right_menu}",
        key=(
            f"right_{st.session_state.game_id}_"
            f"{st.session_state.round_index}_{match_number}"
        ),
        use_container_width=True,
        disabled=st.session_state.selection_locked,
    )

if left_clicked:
    choose_menu(left_menu)
    st.rerun()

if right_clicked:
    choose_menu(right_menu)
    st.rerun()

st.divider()
st.caption(
    "선택 결과는 대결별로 저장됩니다. "
    "이름, 학번, 비밀번호는 수집하지 않습니다."
)
