"""
app.py — Интерактивный веб-интерфейс «Инвест-Квест» для хакатона Т-Банка.

Номинация: Новый пользовательский опыт.
Стек: Streamlit, Plotly, OpenAI API, Tinkoff Invest SDK.
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, Any, List

from data_loader import DataLoader, Scenario
from game_engine import GameEngine, InvestorProfile
from ai_master import AIMaster, DailyEventResponse, FinalReviewResponse

# 1. Настройка страницы
st.set_page_config(
    page_title="Инвест-Квест | Т-Банк",
    page_icon="💛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Фирменные стили Т-Банка (CSS)
T_BANK_CSS = """
<style>
    /* Основные цвета и шрифт */
    :root {
        --tb-yellow: #FFDD2D;
        --tb-dark: #121316;
        --tb-card: #1E2025;
        --tb-border: #2C3038;
        --tb-text-muted: #8F95A3;
        --tb-green: #00C853;
        --tb-red: #FF3B30;
    }

    /* Стилизация карточек */
    .tb-card {
        background-color: var(--tb-card);
        border: 1px solid var(--tb-border);
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }

    .tb-card-accent {
        background-color: var(--tb-card);
        border-left: 4px solid var(--tb-yellow);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }

    /* Комментарии Пульса */
    .pulse-comment {
        background-color: #17181C;
        border: 1px solid #282A30;
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }
    .pulse-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
        font-size: 0.85rem;
    }
    .pulse-author {
        font-weight: 600;
        color: #FFFFFF;
    }
    .pulse-text {
        font-size: 0.92rem;
        line-height: 1.35;
        color: #E1E3E8;
    }

    /* Фирменный бэдж Т-Банка */
    .tb-badge {
        display: inline-block;
        background-color: var(--tb-yellow);
        color: #000000;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 6px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    /* Кнопки действий */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        height: 50px;
        transition: all 0.2s ease-in-out;
    }
</style>
"""
st.markdown(T_BANK_CSS, unsafe_allow_html=True)


# 3. Инициализация состояния сессии
def init_session():
    if "loader" not in st.session_state:
        st.session_state.loader = DataLoader()

    if "ai_master" not in st.session_state:
        st.session_state.ai_master = AIMaster()

    if "scenarios" not in st.session_state:
        st.session_state.scenarios = st.session_state.loader.load_all_scenarios()

    if "scenario_id" not in st.session_state:
        st.session_state.scenario_id = st.session_state.scenarios[0].id

    if "engine" not in st.session_state:
        scenario = st.session_state.loader.get_scenario(st.session_state.scenario_id)
        st.session_state.engine = GameEngine(scenario)

    if "events_cache" not in st.session_state:
        st.session_state.events_cache = {}

    if "final_review" not in st.session_state:
        st.session_state.final_review = None

    if "sandbox_ordered" not in st.session_state:
        st.session_state.sandbox_ordered = False

    if "mentor_chat" not in st.session_state:
        st.session_state.mentor_chat = {}


init_session()
engine: GameEngine = st.session_state.engine
ai_master: AIMaster = st.session_state.ai_master


def restart_game(new_scenario_id: str):
    """Сброс состояния игры на выбранный сценарий."""
    scenario = st.session_state.loader.get_scenario(new_scenario_id)
    st.session_state.scenario_id = new_scenario_id
    st.session_state.engine = GameEngine(scenario)
    st.session_state.events_cache = {}
    st.session_state.final_review = None
    st.session_state.sandbox_ordered = False
    st.session_state.mentor_chat = {}
    st.rerun()


# 4. Сайдбар
with st.sidebar:
    st.markdown("### 💛 Инвест-Квест")
    st.caption("Хакатон Т-Банка • Новый пользовательский опыт")
    st.markdown("---")

    # Выбор сценария
    scenario_options = {s.id: f"{s.disguised_name} ({s.disguised_sector})" for s in st.session_state.scenarios}
    selected_id = st.selectbox(
        "Выберите исторический вызов:",
        options=list(scenario_options.keys()),
        format_func=lambda x: scenario_options[x],
        index=list(scenario_options.keys()).index(st.session_state.scenario_id),
    )

    if selected_id != st.session_state.scenario_id:
        restart_game(selected_id)

    # Карточка выбранного актива
    cur_scen = engine.scenario
    st.markdown(
        f"""
        <div class="tb-card">
            <span class="tb-badge">{cur_scen.disguised_sector}</span>
            <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 4px;">{cur_scen.disguised_name}</div>
            <div style="color: #8F95A3; font-size: 0.85rem;">{cur_scen.disguised_description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Кнопка сброса
    if st.button("🔄 Начать заново", use_container_width=True):
        restart_game(st.session_state.scenario_id)

    st.markdown("---")
    # Статус AI ядра
    st.caption(f"AI Движок: {ai_master.get_status_label()}")

    # Портфельная статистика
    st.markdown("#### 💼 Ваш портфель")
    st.metric(
        label="Общая стоимость",
        value=f"{engine.total_value:,.2f} ₽",
        delta=f"{engine.pnl_pct:+.2f}% ({engine.pnl_rub:+,.2f} ₽)",
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Кэш", f"{engine.cash:,.0f} ₽")
    with col_m2:
        st.metric("Акции", f"{engine.shares} шт.")

    st.markdown("---")
    st.caption("Реальные названия бумаг и даты зашифрованы до конца 10-го дня квеста.")


# 5. Вспомогательная функция для графика Plotly
def build_candlestick_chart(engine: GameEngine, show_all: bool = False):
    """
    Построение красивого темного свечного графика со сделками игрока.
    Во время игры ось X строго строковая ('День 1', 'День 2'...), чтобы не палить даты
    и устранить пустые провалы от выходных дней.
    """
    candles = engine.scenario.candles if show_all else engine.candles_revealed

    # Подписи оси X: во время игры — строго 'День N', в финале — реальные даты
    if show_all:
        x_labels = [c.date for c in candles]
    else:
        x_labels = [f"День {c.step + 1}" for c in candles]

    fig = go.Figure()

    # Свечной график с защитой от спойлеров и кастомным hover
    fig.add_trace(
        go.Candlestick(
            x=x_labels,
            open=[c.open for c in candles],
            high=[c.high for c in candles],
            low=[c.low for c in candles],
            close=[c.close for c in candles],
            name="Котировки",
            increasing_line_color="#00C853",
            decreasing_line_color="#FF3B30",
            increasing_fillcolor="#00C853",
            decreasing_fillcolor="#FF3B30",
            line_width=1.5,
            hovertemplate="<b>%{x}</b><br>Открытие: %{open:,.2f} ₽<br>Максимум: %{high:,.2f} ₽<br>Минимум: %{low:,.2f} ₽<br>Закрытие: %{close:,.2f} ₽<extra></extra>",
        )
    )

    # Нанесение совершенных сделок
    trades = engine.trade_history
    buy_steps = [t for t in trades if t.action == "BUY" and (show_all or t.step <= engine.current_step)]
    sell_steps = [t for t in trades if t.action == "SELL_ALL" and (show_all or t.step <= engine.current_step)]

    if buy_steps:
        fig.add_trace(
            go.Scatter(
                x=[x_labels[t.step] for t in buy_steps],
                y=[candles[t.step].low * 0.985 for t in buy_steps],
                mode="markers+text",
                name="Покупка (BUY)",
                text=["🟢 Покупка" for _ in buy_steps],
                textposition="bottom center",
                marker=dict(symbol="triangle-up", size=14, color="#00C853", line=dict(width=1, color="#FFFFFF")),
                hoverinfo="skip",
            )
        )

    if sell_steps:
        fig.add_trace(
            go.Scatter(
                x=[x_labels[t.step] for t in sell_steps],
                y=[candles[t.step].high * 1.015 for t in sell_steps],
                mode="markers+text",
                name="Продажа (SELL)",
                text=["🔴 Продано" for _ in sell_steps],
                textposition="top center",
                marker=dict(symbol="triangle-down", size=14, color="#FF3B30", line=dict(width=1, color="#FFFFFF")),
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#121316",
        plot_bgcolor="#17181C",
        margin=dict(l=20, r=20, t=55, b=25),
        height=390,
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color="#E1E3E8"),
        ),
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=x_labels,
            showgrid=True,
            gridcolor="#262930",
            color="#8F95A3",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#262930",
            color="#8F95A3",
            side="right",
        ),
    )
    return fig


# 6. Основной экран игры или Экран завершения
if not engine.is_game_over:
    # --- ЭКРАН ХОДА ИГРЫ ---

    # Прогресс-бар и заголовок дня
    step_num = engine.current_step + 1
    total_steps = engine.total_steps
    progress_val = step_num / total_steps

    st.progress(progress_val)

    top_col1, top_col2 = st.columns([2, 1])
    with top_col1:
        st.subheader(f"День {step_num} из {total_steps}: {engine.scenario.disguised_name}")
    with top_col2:
        cur_c = engine.current_candle
        color_sign = "+" if cur_c.change_pct >= 0 else ""
        delta_color = "normal" if cur_c.change_pct >= 0 else "inverse"
        st.metric(
            label="Текущая котировка",
            value=f"{cur_c.close:,.2f} ₽",
            delta=f"{color_sign}{cur_c.change_pct:.2f}% за день",
        )

    # Интерактивный свечной график Plotly
    chart_fig = build_candlestick_chart(engine, show_all=False)
    st.plotly_chart(chart_fig, use_container_width=True, key=f"chart_step_{engine.current_step}")

    # Получение AI-события для текущего шага из кэша или генератора
    if engine.current_step not in st.session_state.events_cache:
        last_trade_dict = engine.trade_history[-1].__dict__ if engine.trade_history else None
        event_resp = ai_master.generate_daily_event(
            scenario_name=engine.scenario.disguised_name,
            scenario_sector=engine.scenario.disguised_sector,
            step=engine.current_step,
            total_steps=total_steps,
            candle_data=cur_c.__dict__,
            last_trade=last_trade_dict,
            portfolio_pnl_pct=engine.pnl_pct,
        )
        st.session_state.events_cache[engine.current_step] = event_resp
    else:
        event_resp = st.session_state.events_cache[engine.current_step]

    # Блок новостей и Пульса в 2 колонки
    col_news, col_pulse = st.columns([1.1, 0.9])

    with col_news:
        st.markdown(
            f"""
            <div class="tb-card-accent">
                <span class="tb-badge">Сводка дня</span>
                <div style="font-size: 1.15rem; font-weight: 700; color: #FFFFFF; margin-bottom: 8px;">
                    {event_resp.headline}
                </div>
                <div style="color: #D1D5DB; font-size: 0.95rem; line-height: 1.45; margin-bottom: 12px;">
                    {event_resp.news_summary}
                </div>
                <div style="background-color: #121316; border-radius: 8px; padding: 10px 14px; border: 1px solid #2B2F38;">
                    <span style="color: #FFDD2D; font-weight: 600; font-size: 0.85rem;">💡 Ментор Т-Инвестиций:</span>
                    <div style="color: #A0A5B2; font-size: 0.9rem; margin-top: 4px;">{event_resp.mentor_feedback}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_pulse:
        st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-weight: 700; font-size: 1.05rem; color: #FFFFFF;">💬 Соцсеть «Пульс»</span>
                <span style="font-size: 0.8rem; color: #8F95A3;">настроения толпы</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for p in event_resp.pulse_comments:
            badge_color = "#00C853" if p.sentiment == "bullish" else ("#FF3B30" if p.sentiment == "bearish" else "#8F95A3")
            badge_text = "Бычий настрой 📈" if p.sentiment == "bullish" else ("Паника 📉" if p.sentiment == "bearish" else "Нейтрально ⚖️")
            st.markdown(
                f"""
                <div class="pulse-comment">
                    <div class="pulse-header">
                        <span class="pulse-author">{p.avatar} {p.author}</span>
                        <span style="color: {badge_color}; font-size: 0.75rem; font-weight: 600;">{badge_text}</span>
                    </div>
                    <div class="pulse-text">{p.text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Интерактивный вопрос AI-аналитику (AI-агент фича)
    with st.expander("💬 Задать вопрос AI-аналитику по текущей ситуации", expanded=False):
        st.caption("Спросите аналитика о причинах движения цены, индикаторах или тактике перед принятием решения:")

        with st.form(key=f"mentor_form_{engine.current_step}", clear_on_submit=False):
            col_q_in, col_q_b = st.columns([4, 1])
            with col_q_in:
                user_q = st.text_input(
                    "Вопрос аналитику:",
                    placeholder="Например: Почему падаем? Стоит ли сейчас усреднять?",
                    label_visibility="collapsed",
                )
            with col_q_b:
                submit_q = st.form_submit_button("Спросить 🤖", use_container_width=True)

            if submit_q and user_q.strip():
                with st.spinner("AI-аналитик изучает стакан и новости..."):
                    mentor_ans = ai_master.ask_mentor(
                        question=user_q.strip(),
                        scenario_name=engine.scenario.disguised_name,
                        scenario_sector=engine.scenario.disguised_sector,
                        step=engine.current_step,
                        candle_data=cur_c.__dict__,
                        portfolio_status={
                            "cash": engine.cash,
                            "shares": engine.shares,
                            "total_value": engine.total_value,
                            "pnl_pct": engine.pnl_pct,
                        },
                    )
                    st.session_state.mentor_chat[engine.current_step] = (user_q.strip(), mentor_ans)

        if engine.current_step in st.session_state.mentor_chat:
            q_txt, a_txt = st.session_state.mentor_chat[engine.current_step]
            st.markdown(
                f"""
                <div style="background-color: #17181C; border-left: 3px solid #FFDD2D; border-radius: 8px; padding: 12px 14px; margin-top: 10px;">
                    <div style="font-size: 0.85rem; color: #8F95A3; margin-bottom: 4px;"><b>Вы спросили:</b> {q_txt}</div>
                    <div style="font-size: 0.92rem; color: #E1E3E8; line-height: 1.45;"><b>🤖 Ответ AI-аналитика:</b> {a_txt}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Панель управления действиями
    st.markdown("---")
    st.markdown("<div style='font-size: 0.9rem; font-weight: 600; color: #8F95A3; margin-bottom: 8px;'>ВАШЕ РЕШЕНИЕ:</div>", unsafe_allow_html=True)

    btn_buy_col, btn_sell_col, btn_hold_col = st.columns(3)

    with btn_buy_col:
        buy_shares_possible = int(engine.cash // engine.current_price)
        buy_label = f"🟢 Купить на всё ({buy_shares_possible} шт.)"
        if st.button(buy_label, use_container_width=True, disabled=not engine.can_buy):
            engine.execute_action("BUY")
            st.rerun()

    with btn_sell_col:
        sell_label = f"🔴 Продать всё ({engine.shares} шт.)"
        if st.button(sell_label, use_container_width=True, disabled=not engine.can_sell):
            engine.execute_action("SELL_ALL")
            st.rerun()

    with btn_hold_col:
        if st.button("🟡 Держать / Ждать", use_container_width=True):
            engine.execute_action("HOLD")
            st.rerun()

else:
    # --- ФИНАЛЬНЫЙ ЭКРАН (РАСКРЫТИЕ ИТОГОВ И АНАЛИТИКА) ---
    summary = engine.get_summary()
    profile = summary["profile"]

    # Эффект конфетти при успехе
    if summary["pnl_pct"] > 0:
        st.balloons()

    st.markdown(
        f"""
        <div style="text-align: center; margin-bottom: 24px;">
            <div class="tb-badge" style="font-size: 0.9rem; padding: 4px 12px;">КВЕСТ ЗАВЕРШЕН</div>
            <h1 style="color: #FFFFFF; margin-top: 4px;">Раскрытие карт: Это был {summary['real_name']} ({summary['real_ticker']})</h1>
            <p style="color: #8F95A3; font-size: 1.1rem;">Период: {summary['real_period']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Ключевые финансовые метрики
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric(
            label="Итоговый результат портфеля",
            value=f"{summary['final_value']:,.2f} ₽",
            delta=f"{summary['pnl_pct']:+.2f}% ({summary['pnl_rub']:+,.2f} ₽)",
        )
    with col_res2:
        st.metric(
            label="Бенчмарк «Купи и держи»",
            value=f"{summary['benchmark_pnl_pct']:+.2f}%",
            delta=f"{summary['benchmark_pnl_pct']:+.2f}%",
        )
    with col_res3:
        alpha = summary["alpha_pct"]
        alpha_sign = "+" if alpha >= 0 else ""
        st.metric(
            label="Альфа (Опережение рынка)",
            value=f"{alpha_sign}{alpha:.2f}%",
            delta=f"{alpha_sign}{alpha:.2f}% к рынку",
        )

    st.markdown("---")

    # Полный свечной график с раскрытыми датами и сделками
    st.markdown("#### 📊 Полная картина исторического шторма")
    full_chart = build_candlestick_chart(engine, show_all=True)
    st.plotly_chart(full_chart, use_container_width=True, key="full_chart_final")

    # Генерация или загрузка финального AI-разбора
    if st.session_state.final_review is None:
        st.session_state.final_review = ai_master.generate_final_review(summary)
    review: FinalReviewResponse = st.session_state.final_review

    # Блок Профиля инвестора и AI-разбора
    col_prof, col_rev = st.columns([1, 1.2])

    with col_prof:
        st.markdown(
            f"""
            <div class="tb-card-accent" style="height: 100%;">
                <span class="tb-badge">Ваш архетип инвестора</span>
                <div style="font-size: 2rem; margin: 8px 0;">{profile['badge']} <b>{profile['title']}</b></div>
                <div style="color: #D1D5DB; font-size: 0.95rem; line-height: 1.4; margin-bottom: 14px;">
                    {profile['description']}
                </div>
                <div style="margin-top: 10px;">
                    <div style="font-weight: 600; color: #FFDD2D; font-size: 0.85rem; margin-bottom: 6px;">Ключевые черты:</div>
                    {"".join(f'<div style="color: #A0A5B2; font-size: 0.85rem;">• {ch}</div>' for ch in profile['characteristics'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_rev:
        st.markdown(
            f"""
            <div class="tb-card" style="height: 100%;">
                <span class="tb-badge" style="background-color: #2C3038; color: #FFFFFF;">Вердикт AI-консультанта</span>
                <div style="color: #FFFFFF; font-size: 1rem; line-height: 1.45; margin: 10px 0;">
                    {review.verdict}
                </div>
                <div style="background-color: #121316; border-radius: 8px; padding: 10px 14px; margin: 10px 0;">
                    <div style="font-size: 0.85rem; color: #00C853; font-weight: 600;">Сильные стороны:</div>
                    <div style="font-size: 0.85rem; color: #D1D5DB;">{", ".join(review.strengths)}</div>
                    <div style="font-size: 0.85rem; color: #FFDD2D; font-weight: 600; margin-top: 6px;">Рекомендация:</div>
                    <div style="font-size: 0.85rem; color: #D1D5DB;">{review.recommendations}</div>
                </div>
                <div style="font-style: italic; color: #8F95A3; font-size: 0.85rem;">
                    {review.quote}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- БИЗНЕС-ФИЧА ДЛЯ ХАКАТОНА: Синергия с Т-Инвестициями ---
    st.markdown("---")
    st.markdown(
        """
        <div style="background: linear-gradient(90deg, #1E2025 0%, #282B33 100%); border: 1px solid #FFDD2D; border-radius: 14px; padding: 20px; margin-top: 10px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <span class="tb-badge">Продуктовая интеграция Т-Банка</span>
                    <h3 style="color: #FFFFFF; margin: 4px 0;">Собрать защитный портфель в Т-Инвестициях</h3>
                    <p style="color: #A0A5B2; font-size: 0.95rem; margin: 0;">
                        На основе вашего стиля игры и выявленных зон риска мы подобрали готовую корзину фондов T-Capital.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Рекомендованные продукты в зависимости от профиля
    if profile["title"] in ("Осторожный Хранитель", "Жертва Паники"):
        rec_products = [
            ("🟡 Золото (TGLD)", "Защита от девальвации и паники на рынках", "35%"),
            ("🛡️ Вечный Портфель (TRUR)", "Сбалансированное распределение 4 активов", "40%"),
            ("📈 ОФЗ / Бонды Ликвидности (LQDT)", "Ежедневный гарантированный процент ставки ЦБ", "25%"),
        ]
    else:
        rec_products = [
            ("🚀 Индекс Мосбиржи (TMOS)", "Широкий рынок топ-акций РФ с нулевой комиссией", "50%"),
            ("🟡 Золото (TGLD)", "Защитная доля на случай коррекций", "20%"),
            ("💼 Ликвидность (LQDT)", "Оперативный кэш для покупок на просадках", "30%"),
        ]

    cols_rec = st.columns(3)
    for i, (prod_name, prod_desc, prod_share) in enumerate(rec_products):
        with cols_rec[i]:
            st.markdown(
                f"""
                <div class="tb-card" style="text-align: center; margin-top: 12px;">
                    <div style="font-size: 1.3rem; font-weight: 700; color: #FFDD2D;">{prod_share}</div>
                    <div style="font-weight: 600; color: #FFFFFF; margin: 4px 0;">{prod_name}</div>
                    <div style="font-size: 0.8rem; color: #8F95A3;">{prod_desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Интерактивная кнопка симуляции Sandbox API
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    if not st.session_state.sandbox_ordered:
        if st.button("🚀 Сформировать демо-портфель в Sandbox API Т-Инвестиций", use_container_width=True):
            st.session_state.sandbox_ordered = True
            st.rerun()
    else:
        st.success(
            "🎉 Заявка успешно исполнена в Sandbox API Т-Инвестиций!\n\n"
            "• Аккаунт: `T-INVEST-DEMO-QUEST-777`\n"
            "• Статус ордеров: `EXECUTED`\n"
            "• Комиссия брокера за покупку фондов Т-Банка: `0 ₽`\n"
            "• Баланс переведен в защитную диверсифицированную структуру."
        )

    # Кнопка перезапуска квеста
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    if st.button("🎮 Сыграть ещё раз в другой сценарий", use_container_width=True):
        # Переключаем на следующий сценарий
        all_ids = [s.id for s in st.session_state.scenarios]
        cur_idx = all_ids.index(st.session_state.scenario_id)
        next_id = all_ids[(cur_idx + 1) % len(all_ids)]
        restart_game(next_id)
