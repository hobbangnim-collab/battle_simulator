from pathlib import Path

import pandas as pd
import streamlit as st

from simulator_v3 import Unit, load_equipment_skills, load_generals, load_tactics, run_batch, simulate_battle


BASE_DIR = Path(__file__).resolve().parent
GENERAL_PATH = BASE_DIR / "data" / "generals.csv"
TACTIC_PATH = BASE_DIR / "data" / "tactics.csv"
EQUIPMENT_SKILL_PATH = BASE_DIR / "data" / "equipment_skills.csv"
TIER_TABLE_PATH = BASE_DIR / "static" / "hero_tier_table.pdf"
TIER_TABLE_STATIC_URL = "app/static/hero_tier_table.pdf"


st.set_page_config(page_title="삼국지전략판 차차의 전략 서포터", layout="wide")
st.title("삼국지전략판 차차의 전략 서포터")
st.caption("티어표 확인, 장수 데이터 정리, 전투 흐름 실험을 한곳에서 다루는 개인 전략 도구입니다.")
st.markdown(
    """
    **Beta 1.0 Version**  
    티어표 빠른 확인 · 장수/전법/장비 데이터 관리 · 실제 로그 구조 기반 전투 시뮬레이션 테스트
    """
)

tactics = load_tactics(TACTIC_PATH)
equipment_skills = load_equipment_skills(EQUIPMENT_SKILL_PATH)
generals = load_generals(GENERAL_PATH, tactics)
names = list(generals.keys())
tactic_names = [""] + list(tactics.keys())
equipment_slots = ["무기", "갑옷", "탈것", "보물"]
equipment_names_by_slot = {
    slot: [""] + [name for name, skill in equipment_skills.items() if skill.slot == slot]
    for slot in equipment_slots
}
troop_types = ["기병", "창병", "궁병", "방패병", "병기"]
aptitudes = ["S", "A", "B", "C"]
advancements = ["단무지", "1돌", "2돌", "3돌", "4돌", "풀돌", "컬풀돌"]
advancement_bonus_points = {
    "단무지": 0,
    "1돌": 10,
    "2돌": 20,
    "3돌": 30,
    "4돌": 40,
    "풀돌": 50,
    "컬풀돌": 60,
}
bonus_stats = ["무력", "지력", "통솔", "속도", "매력", "정치"]
stat_specs = [
    ("무력", "base_force"),
    ("지력", "base_intellect"),
    ("통솔", "base_command"),
    ("속도", "base_speed"),
    ("매력", "base_charm"),
    ("정치", "base_politics"),
]


def load_general_rows():
    frame = pd.read_csv(GENERAL_PATH, encoding="utf-8-sig")
    return {row["장수"]: row.to_dict() for _, row in frame.iterrows()}


general_source_rows = load_general_rows()


def stat_total(row, stat):
    level = int(row.get("레벨", 1))
    return int(float(row[f"기본{stat}"]) + float(row[f"{stat}성장"]) * max(0, level - 1) + float(row[f"{stat}투자"]))


def stat_before_invest(row, stat):
    level = int(row.get("레벨", 1))
    return float(row[f"기본{stat}"]) + float(row[f"{stat}성장"]) * max(0, level - 1)


def available_bonus(row):
    level = int(row.get("레벨", 1))
    image_bonus = int(float(row.get("이미지보너스", 0)))
    advancement_bonus = advancement_bonus_points.get(str(row.get("돌파", "단무지")), 0)
    return (level // 10) * 10 + advancement_bonus + image_bonus


def level_bonus(row):
    return (int(row.get("레벨", 1)) // 10) * 10


def advancement_bonus(row):
    return advancement_bonus_points.get(str(row.get("돌파", "단무지")), 0)


def used_bonus(row):
    return int(sum(float(row.get(f"{stat}투자", 0)) for stat in bonus_stats))


def army_rows(selected_names):
    rows = []
    roles = ["주장", "부장1", "부장2"]
    for position, name in enumerate(selected_names, start=1):
        general = generals[name]
        source = general_source_rows.get(name, {})
        tactic_slots = list(general.tactics) + [None, None, None]
        rows.append(
            {
                "역할": roles[position - 1] if position <= len(roles) else str(position),
                "장수": general.name,
                "레벨": int(source.get("레벨", 50)),
                "돌파": str(source.get("돌파", "단무지")),
                "이미지보너스": int(source.get("이미지보너스", 0)),
                "기본무력": float(source.get("기본무력", general.base_force)),
                "무력성장": float(source.get("무력성장", 0)),
                "무력투자": float(source.get("무력투자", source.get("무력보너스", 0))),
                "기본지력": float(source.get("기본지력", general.base_intellect)),
                "지력성장": float(source.get("지력성장", 0)),
                "지력투자": float(source.get("지력투자", source.get("지력보너스", 0))),
                "기본통솔": float(source.get("기본통솔", general.base_command)),
                "통솔성장": float(source.get("통솔성장", 0)),
                "통솔투자": float(source.get("통솔투자", source.get("통솔보너스", 0))),
                "기본속도": float(source.get("기본속도", general.base_speed)),
                "속도성장": float(source.get("속도성장", 0)),
                "속도투자": float(source.get("속도투자", source.get("속도보너스", 0))),
                "기본매력": float(source.get("기본매력", general.base_charm)),
                "매력성장": float(source.get("매력성장", 0)),
                "매력투자": float(source.get("매력투자", source.get("매력보너스", 0))),
                "기본정치": float(source.get("기본정치", general.base_politics)),
                "정치성장": float(source.get("정치성장", 0)),
                "정치투자": float(source.get("정치투자", source.get("정치보너스", 0))),
                "병력": 10000,
                "병종": general.troop_type,
                "기병적성": general.cavalry_aptitude,
                "창병적성": general.spear_aptitude,
                "궁병적성": general.bow_aptitude,
                "방패병적성": general.shield_aptitude,
                "병기적성": general.siege_aptitude,
                "전법1": tactic_slots[0].name if tactic_slots[0] else "",
                "전법2": tactic_slots[1].name if tactic_slots[1] else "",
                "전법3": tactic_slots[2].name if tactic_slots[2] else "",
                "무기": "",
                "갑옷": "",
                "탈것": "",
                "보물": "",
            }
        )
    return pd.DataFrame(rows)


def rows_to_army(rows):
    army = []
    for row in rows.to_dict("records"):
        tactic_list = [
            tactics[name]
            for name in [row.get("전법1", ""), row.get("전법2", ""), row.get("전법3", "")]
            if name in tactics
        ]
        for slot in equipment_slots:
            equipment_name = row.get(slot, "")
            if equipment_name in equipment_skills:
                tactic_list.append(equipment_skills[equipment_name].tactic)
        army.append(
            Unit(
                name=str(row["장수"]),
                base_force=stat_total(row, "무력"),
                base_intellect=stat_total(row, "지력"),
                base_command=stat_total(row, "통솔"),
                base_speed=stat_total(row, "속도"),
                base_charm=stat_total(row, "매력"),
                base_politics=stat_total(row, "정치"),
                max_troops=int(row["병력"]),
                troops=int(row["병력"]),
                troop_type=str(row["병종"]),
                aptitude=str(row[f"{row['병종']}적성"]),
                cavalry_aptitude=str(row["기병적성"]),
                spear_aptitude=str(row["창병적성"]),
                bow_aptitude=str(row["궁병적성"]),
                shield_aptitude=str(row["방패병적성"]),
                siege_aptitude=str(row["병기적성"]),
                morale=100.0,
                tactics=tactic_list,
                role=str(row["역할"]),
                advancement=str(row["돌파"]),
                equipment={slot: str(row.get(slot, "")) for slot in equipment_slots if row.get(slot, "")},
            )
        )
    return army


def widget_key(side_key, index, name, field):
    return f"{side_key}_{index}_{name}_{field}"


def render_stat_invest(row, stat, side_key, index):
    invest_key = widget_key(side_key, index, row["장수"], f"{stat}_invest")
    base_value = stat_before_invest(row, stat)
    stat_cols = st.columns([0.9, 1.8, 1.0], vertical_alignment="center")

    with stat_cols[2]:
        current_invest = st.number_input(
            f"{stat} 투자",
            min_value=0,
            max_value=120,
            step=1,
            value=int(float(row.get(f"{stat}투자", 0))),
            key=invest_key,
            label_visibility="collapsed",
        )

    row[f"{stat}투자"] = int(current_invest)
    current_value = base_value + int(current_invest)

    with stat_cols[0]:
        st.markdown(f"**{stat}**")
    with stat_cols[1]:
        st.markdown(f"{base_value:.0f} → **{current_value:.0f}**")
    return row


def render_general_card(row, side_key, index):
    with st.container(border=True):
        st.markdown(f"### {row['역할']} · {row['장수']}")

        level_col, troop_col, advance_col, image_col, troop_type_col = st.columns([1, 1, 1, 1, 1])
        with level_col:
            row["레벨"] = st.slider(
                "레벨",
                1,
                50,
                int(row["레벨"]),
                key=widget_key(side_key, index, row["장수"], "level"),
            )
        with troop_col:
            row["병력"] = st.number_input(
                "병력",
                min_value=0,
                max_value=10000,
                step=100,
                value=int(row["병력"]),
                key=widget_key(side_key, index, row["장수"], "troops"),
            )
        with advance_col:
            row["돌파"] = st.selectbox(
                "돌파",
                advancements,
                index=advancements.index(str(row["돌파"])) if str(row["돌파"]) in advancements else 0,
                key=widget_key(side_key, index, row["장수"], "advancement"),
            )
        with image_col:
            row["이미지보너스"] = st.selectbox(
                "이미지",
                [0, 10],
                index=1 if int(float(row["이미지보너스"])) == 10 else 0,
                format_func=lambda value: "+10" if value else "없음",
                key=widget_key(side_key, index, row["장수"], "image_bonus"),
            )
        with troop_type_col:
            row["병종"] = st.selectbox(
                "병종",
                troop_types,
                index=troop_types.index(str(row["병종"])) if str(row["병종"]) in troop_types else 0,
                key=widget_key(side_key, index, row["장수"], "troop_type"),
            )

        st.caption(
            f"포인트: 레벨 {level_bonus(row)} + 돌파 {advancement_bonus(row)} + 이미지 {int(float(row['이미지보너스']))}"
            f" = {available_bonus(row)} / 사용 {used_bonus(row)}"
        )

        st.markdown("**스탯 투자**")
        for stat in bonus_stats:
            row = render_stat_invest(row, stat, side_key, index)

        point_a, point_b, point_c, point_d = st.columns(4)
        point_a.metric("가능", available_bonus(row))
        point_b.metric("사용", used_bonus(row))
        point_c.metric("잔여", available_bonus(row) - used_bonus(row))
        point_d.metric("이미지", f"+{int(float(row['이미지보너스']))}")

        with st.expander("병종 적성 / 전법 / 장비"):
            apt_cols = st.columns(5)
            for col, troop_type in zip(apt_cols, troop_types):
                with col:
                    key = f"{troop_type}적성"
                    row[key] = st.selectbox(
                        key,
                        aptitudes,
                        index=aptitudes.index(str(row[key])) if str(row[key]) in aptitudes else 2,
                        key=widget_key(side_key, index, row["장수"], key),
                    )

            tactic_cols = st.columns(3)
            for slot, col in enumerate(tactic_cols, start=1):
                field = f"전법{slot}"
                with col:
                    current = str(row.get(field, ""))
                    row[field] = st.selectbox(
                        field,
                        tactic_names,
                        index=tactic_names.index(current) if current in tactic_names else 0,
                        key=widget_key(side_key, index, row["장수"], field),
                    )

            equipment_cols = st.columns(4)
            for col, slot in zip(equipment_cols, equipment_slots):
                with col:
                    options = equipment_names_by_slot[slot]
                    current = str(row.get(slot, ""))
                    row[slot] = st.selectbox(
                        slot,
                        options,
                        index=options.index(current) if current in options else 0,
                        key=widget_key(side_key, index, row["장수"], slot),
                    )

    return row


def render_army_editor(selected_names, side_label, side_key):
    st.subheader(f"{side_label} 부대 세팅")
    rows = []
    for index, row in enumerate(army_rows(selected_names).to_dict("records"), start=1):
        rows.append(render_general_card(row, side_key, index))
    return pd.DataFrame(rows)

tier_tab, battle_tab, general_tab = st.tabs(["티어표", "전투 시뮬", "장수 데이터"])

with battle_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("아군")
        army_a_names = st.multiselect("아군 장수", names, default=["SP마초", "SP황보숭", "허유"], max_selections=3)
    with right:
        st.subheader("적군")
        army_b_names = st.multiselect("적군 장수", names, default=["SP마초", "SP황보숭", "허유"], max_selections=3)

    count = st.slider("반복 전투", 1, 5000, 500, step=50)
    seed = st.number_input(
        "시드",
        value=1,
        step=1,
        help="랜덤값입니다. 같은 시드와 같은 세팅이면 같은 결과가 나오며, 전법 발동률과 대상 선택 같은 확률 흐름에 영향을 줍니다.",
    )
    st.caption("시드: 랜덤값입니다. 같은 값이면 같은 결과가 나오며, 확률 흐름을 재현할 때 사용합니다.")

    if len(army_a_names) != 3 or len(army_b_names) != 3:
        st.warning("각 부대에 장수 3명을 선택하세요.")
        st.stop()

    st.subheader("전투 입력값")
    st.caption("장수별로 레벨, 돌파, 병력, 스탯 투자, 전법을 조정합니다. 여기서 바꾼 값은 이번 실행에만 적용됩니다.")
    edit_a, edit_b = st.columns(2)
    with edit_a:
        edited_a = render_army_editor(army_a_names, "아군", "army_a")
    with edit_b:
        edited_b = render_army_editor(army_b_names, "적군", "army_b")

    army_a = rows_to_army(edited_a)
    army_b = rows_to_army(edited_b)

    bonus_rows = []
    for side_name, frame in [("아군", edited_a), ("적군", edited_b)]:
        for row in frame.to_dict("records"):
            bonus_rows.append(
                {
                    "진영": side_name,
                    "역할": row["역할"],
                    "장수": row["장수"],
                    "레벨": int(row["레벨"]),
                    "돌파": row["돌파"],
                    "레벨 포인트": level_bonus(row),
                    "돌파 포인트": advancement_bonus(row),
                    "이미지 포인트": int(float(row.get("이미지보너스", 0))),
                    "투자 포인트": used_bonus(row),
                    "가능 포인트": available_bonus(row),
                    "잔여": available_bonus(row) - used_bonus(row),
                }
            )

    st.subheader("계산된 최종 스탯")
    final_rows = []
    for side_name, army in [("아군", army_a), ("적군", army_b)]:
        for unit in army:
            final_rows.append(
                {
                    "진영": side_name,
                    "역할": unit.role,
                    "장수": unit.name,
                    "돌파": unit.advancement,
                    "무력": unit.base_force,
                    "지력": unit.base_intellect,
                    "통솔": unit.base_command,
                    "속도": unit.base_speed,
                    "매력": unit.base_charm,
                    "정치": unit.base_politics,
                    "병력": unit.max_troops,
                    "병종": unit.troop_type,
                    "장비": " / ".join(unit.equipment.values()),
                }
            )
    st.dataframe(pd.DataFrame(final_rows), width="stretch", hide_index=True)

    st.subheader("스탯 투자 포인트")
    bonus_frame = pd.DataFrame(bonus_rows)
    st.dataframe(bonus_frame, width="stretch", hide_index=True)
    overspent = bonus_frame[bonus_frame["잔여"] < 0]
    if not overspent.empty:
        st.error("스탯 투자 포인트를 사용 가능 포인트보다 많이 투자한 장수가 있습니다.")
        st.stop()

    if st.button("시뮬레이션 실행", type="primary"):
        batch = run_batch(army_a, army_b, count, seed=int(seed))
        win_a = sum(1 for result in batch if result.winner == "A")
        win_b = sum(1 for result in batch if result.winner == "B")
        draws = count - win_a - win_b
        avg_a = sum(result.left_a for result in batch) / count
        avg_b = sum(result.left_b for result in batch) / count

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("아군 승률", f"{win_a / count:.1%}")
        c2.metric("적군 승률", f"{win_b / count:.1%}")
        c3.metric("무승부", draws)
        c4.metric("평균 잔여 병력", f"아군 {avg_a:,.0f} / 적군 {avg_b:,.0f}")

        summary = pd.DataFrame(
            [
                {"진영": "아군", "승리": win_a, "승률": win_a / count, "평균 잔여 병력": avg_a},
                {"진영": "적군", "승리": win_b, "승률": win_b / count, "평균 잔여 병력": avg_b},
                {"진영": "무승부", "승리": draws, "승률": draws / count, "평균 잔여 병력": 0},
            ]
        )
        st.dataframe(summary, width="stretch", hide_index=True)

        sample = simulate_battle(army_a, army_b, seed=int(seed), keep_log=True)
        st.subheader("샘플 전투 로그")
        log_tabs = st.tabs(list(sample.log_sections.keys()))
        for tab, (section, lines) in zip(log_tabs, sample.log_sections.items()):
            with tab:
                st.code("\n".join(lines), language="text")

with general_tab:
    st.subheader("장수 데이터")
    general_rows = []
    for general in generals.values():
        general_rows.append(
            {
                "장수": general.name,
                "무력": general.base_force,
                "지력": general.base_intellect,
                "통솔": general.base_command,
                "속도": general.base_speed,
                "매력": general.base_charm,
                "정치": general.base_politics,
                "병력": general.max_troops,
                "기본병종": general.troop_type,
                "기병적성": general.cavalry_aptitude,
                "창병적성": general.spear_aptitude,
                "궁병적성": general.bow_aptitude,
                "방패병적성": general.shield_aptitude,
                "병기적성": general.siege_aptitude,
                "전법": " / ".join(tactic.name for tactic in general.tactics),
            }
        )
    st.dataframe(pd.DataFrame(general_rows), width="stretch", hide_index=True)

    st.subheader("장비 스킬 데이터")
    equipment_rows = []
    for skill in equipment_skills.values():
        equipment_rows.append(
            {
                "장비명": skill.equipment_name,
                "장비종류": skill.slot,
                "스킬명": skill.tactic.name.split(" - ", 1)[-1],
                "발동시점": skill.tactic.phase,
                "효과유형": skill.tactic.type,
                "발동률": skill.tactic.rate,
                "계수": skill.tactic.power,
                "대상": skill.tactic.target,
                "지속턴": skill.tactic.turns,
                "상태": skill.tactic.status,
            }
        )
    st.dataframe(pd.DataFrame(equipment_rows), width="stretch", hide_index=True)

with tier_tab:
    st.subheader("티어표")
    if TIER_TABLE_PATH.exists():
        pdf_bytes = TIER_TABLE_PATH.read_bytes()
        st.link_button("새 창에서 PDF 열기", TIER_TABLE_STATIC_URL)
        st.download_button(
            "PDF 다운로드",
            data=pdf_bytes,
            file_name="hero_tier_table.pdf",
            mime="application/pdf",
        )
        st.markdown(
            f"""
            <iframe
                src="/{TIER_TABLE_STATIC_URL}#toolbar=1&navpanes=1&view=FitH"
                width="100%"
                height="900px"
                style="border: 1px solid #ddd; border-radius: 6px; background: #fff;"
            ></iframe>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("티어표 PDF 파일을 찾을 수 없습니다.")
