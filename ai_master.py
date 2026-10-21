"""
ai_master.py — AI-генератор новостей, мнений соцсети «Пульс» и аналитики ментора.

Поддерживает:
1. OpenAI-совместимый API (OpenAI, DeepSeek, OpenRouter, vLLM) с JSON-ответами.
2. Безопасный Offline Fallback режим (если нет ключа или API вернул ошибку,
   приложение мгновенно генерирует реалистичный контекстный контент на базе scenarios.json).
3. Финальный разбор полетов и персональные рекомендации по итогам игры.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


@dataclass
class PulseComment:
    author: str
    avatar: str
    sentiment: str  # "bullish", "bearish", "neutral"
    text: str


@dataclass
class DailyEventResponse:
    headline: str
    news_summary: str
    mentor_feedback: str
    pulse_comments: List[PulseComment]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline": self.headline,
            "news_summary": self.news_summary,
            "mentor_feedback": self.mentor_feedback,
            "pulse_comments": [asdict(c) for c in self.pulse_comments],
        }


@dataclass
class FinalReviewResponse:
    verdict: str
    strengths: List[str]
    mistakes: List[str]
    recommendations: str
    quote: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AIMaster:
    """Управление взаимодействием с LLM и генерацией игрового контента."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.client: Optional[OpenAI] = None

        if self.api_key and OpenAI is not None:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception as e:
                print(f"[AIMaster] Ошибка инициализации OpenAI клиента: {e}")
                self.client = None

    @property
    def is_online(self) -> bool:
        """Доступен ли сейчас онлайн-режим LLM."""
        return self.client is not None

    def get_status_label(self) -> str:
        """Информационный статус для сайдбара."""
        if self.is_online:
            return f"🟢 Онлайн LLM ({self.model})"
        return "🟡 Демо-режим (Локальный ИИ)"

    def generate_daily_event(
        self,
        scenario_name: str,
        scenario_sector: str,
        step: int,
        total_steps: int,
        candle_data: Dict[str, Any],
        last_trade: Optional[Dict[str, Any]] = None,
        portfolio_pnl_pct: float = 0.0,
    ) -> DailyEventResponse:
        """
        Генерация карточки дня: новость, комментарий ментора и 2 поста из 'Пульса'.
        При сбое сети или отсутствии ключа срабатывает оффлайн генератор.
        """
        if self.is_online and self.client is not None:
            try:
                return self._generate_daily_event_llm(
                    scenario_name=scenario_name,
                    scenario_sector=scenario_sector,
                    step=step,
                    total_steps=total_steps,
                    candle_data=candle_data,
                    last_trade=last_trade,
                    portfolio_pnl_pct=portfolio_pnl_pct,
                )
            except Exception as e:
                print(f"[AIMaster] Ошибка вызова LLM: {e}. Переключение на fallback-генератор.")

        # Fallback генератор
        return self._generate_fallback_daily_event(
            scenario_name=scenario_name,
            step=step,
            candle_data=candle_data,
            last_trade=last_trade,
            portfolio_pnl_pct=portfolio_pnl_pct,
        )

    def _generate_daily_event_llm(
        self,
        scenario_name: str,
        scenario_sector: str,
        step: int,
        total_steps: int,
        candle_data: Dict[str, Any],
        last_trade: Optional[Dict[str, Any]],
        portfolio_pnl_pct: float,
    ) -> DailyEventResponse:
        """Вызов LLM API с принудительным форматом JSON."""
        system_prompt = (
            "Ты — ведущий интерактивной биржевой игры 'Инвест-Квест' от Т-Банка. "
            "Твоя задача — генерировать атмосферные новости дня, краткий фидбек финансового ментора "
            "и яркие комментарии трейдеров из социальной сети 'Пульс' (паникёра и оптимиста). "
            "ВАЖНО: Никогда не называй реальный тикер или год — используй замаскированное имя актива. "
            "Отвечай строго в формате валидного JSON со следующей структурой:\n"
            "{\n"
            '  "headline": "Краткий броский заголовок дня",\n'
            '  "news_summary": "1-2 предложения о событиях дня и реакции рынка",\n'
            '  "mentor_feedback": "1 предложение — оценка прошлого действия игрока или напутствие",\n'
            '  "pulse_comments": [\n'
            '    {"author": "Ник_Медведя", "avatar": "🐻", "sentiment": "bearish", "text": "Эмоциональный комментарий паникёра"},\n'
            '    {"author": "Ник_Быка", "avatar": "🚀", "sentiment": "bullish", "text": "Эмоциональный комментарий оптимиста"}\n'
            "  ]\n"
            "}"
        )

        user_content = {
            "asset_name": scenario_name,
            "sector": scenario_sector,
            "day": step + 1,
            "total_days": total_steps,
            "today_change_pct": candle_data.get("change_pct", 0.0),
            "today_close_price": candle_data.get("close", 0.0),
            "historical_hint": candle_data.get("news_hint", ""),
            "player_last_action": last_trade.get("action") if last_trade else "START",
            "player_portfolio_pnl_pct": portfolio_pnl_pct,
        }

        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
            temperature=0.7,
            timeout=8.0,
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)

        pulse = [
            PulseComment(
                author=c.get("author", "Инвестор_Пульса"),
                avatar=c.get("avatar", "💬"),
                sentiment=c.get("sentiment", "neutral"),
                text=c.get("text", "..."),
            )
            for c in data.get("pulse_comments", [])
        ]

        # Гарантируем наличие хотя бы 2 комментариев
        if len(pulse) < 2:
            pulse = self._get_fallback_pulse_comments(candle_data.get("change_pct", 0.0))

        return DailyEventResponse(
            headline=data.get("headline", f"Торговый день #{step + 1}"),
            news_summary=data.get("news_summary", candle_data.get("news_hint", "Рынок в ожидании новостей.")),
            mentor_feedback=data.get("mentor_feedback", "Держите эмоции под контролем."),
            pulse_comments=pulse,
        )

    def _generate_fallback_daily_event(
        self,
        scenario_name: str,
        step: int,
        candle_data: Dict[str, Any],
        last_trade: Optional[Dict[str, Any]],
        portfolio_pnl_pct: float,
    ) -> DailyEventResponse:
        """Офлайн-генератор на базе сценария и правил."""
        change_pct = candle_data.get("change_pct", 0.0)
        news_hint = candle_data.get("news_hint", "Торги проходят в штатном режиме.")

        # Заголовок
        if change_pct > 3.0:
            headline = f"🚀 Мощный импульс: {scenario_name} прибавляет {change_pct:+.2f}%"
        elif change_pct > 0:
            headline = f"📈 Умеренный рост: котировки закрылись в плюсе ({change_pct:+.2f}%)"
        elif change_pct < -5.0:
            headline = f"⚡ Обвал котировок: распродажи ускоряются ({change_pct:+.2f}%)"
        elif change_pct < 0:
            headline = f"📉 Давление продавцов: актив просел на {change_pct:+.2f}%"
        else:
            headline = f"⚖️ Боковик: рынок консолидируется в ожидании триггеров"

        # Фидбек ментора по последнему действию
        mentor_feedback = self._get_fallback_mentor_feedback(last_trade, change_pct, step)

        # Комментарии Пульса
        pulse_comments = self._get_fallback_pulse_comments(change_pct)

        return DailyEventResponse(
            headline=headline,
            news_summary=news_hint,
            mentor_feedback=mentor_feedback,
            pulse_comments=pulse_comments,
        )

    def _get_fallback_mentor_feedback(
        self, last_trade: Optional[Dict[str, Any]], today_change_pct: float, step: int
    ) -> str:
        """Оценка прошлого решения игрока от ментора."""
        if step == 0 or not last_trade:
            return "Добро пожаловать в рыночный квест! Изучите первую свечу и решите: рискнуть прямо сейчас или понаблюдать."

        action = last_trade.get("action", "HOLD")

        if action == "BUY":
            if today_change_pct > 0:
                return f"Отличный вход! Ваша покупка сразу вышла в плюс ({today_change_pct:+.2f}%). Не забывайте о фиксации."
            else:
                return f"Смелая покупка на просадке. Рынок пока идет вниз ({today_change_pct:+.2f}%), но инвестор мыслит горизонтом."

        if action == "SELL_ALL":
            if today_change_pct < 0:
                return f"Блестящий тайминг! Вы вышли в кэш и спасли депозит от сегодняшней просадки ({today_change_pct:+.2f}%)."
            else:
                return f"Вы зафиксировали кэш, но актив продолжил расти ({today_change_pct:+.2f}%). Зато капитал в безопасности."

        # HOLD
        if today_change_pct < -3.0:
            return "Вы стойко переносите просадку, не поддаваясь панике толпы. Выдержка — ключевой навык инвестора."
        elif today_change_pct > 3.0:
            return "Удержание позиции приносит плоды! Рост продолжается без лишней суеты с комиссиями."
        return "В боковике выжидательная позиция часто оказывается самой разумной стратегией."

    def _get_fallback_pulse_comments(self, change_pct: float) -> List[PulseComment]:
        """Генерация характерных комментариев сообщества 'Пульс'."""
        if change_pct < -3.0:
            bear_text = random.choice([
                "Сливайте пока не поздно, дна нет! 📉 В стакане одни айсберги на продажу...",
                "Кто брал на хаях — соболезную. Я в кэш на 100%, пересижу под одеялом 😱",
                "ЦБ, остановите торги! Зачем я полез в эту ракету без стопов?! 💀",
            ])
            bull_text = random.choice([
                "Паникёры отдают акции с дисконтом, спасибо! Добираю лесенкой 🛒🚀",
                "Шортистов вынесут вперёд ногами на отскоке. Усредняюсь на всю котлету! 💎",
                "Спокойствие, это просто стряхивание слабых рук перед полётом на Луну 🌙",
            ])
        elif change_pct > 3.0:
            bear_text = random.choice([
                "Ложный пробой, крупняк разгружается об хомяков! Скоро польёмся вниз 🪤",
                "Перекупленность по RSI зашкаливает. Открываю шорт с плечом 🐻",
                "Не ведитесь на зелёные свечи, фундаментала под этим ростом ноль 📉",
            ])
            bull_text = random.choice([
                "Я же говорил — ракета заправлена! Все на борт, летим на новые хаи! 🚀🔥",
                "Шортисты, как вам платится за перенос позиций? Растём дальше! 🤑",
                "Закрыл месяц в жирный плюс! Спасибо лучшему брокеру за мгновенное исполнение 💛",
            ])
        else:
            bear_text = random.choice([
                "Боковик уже укачал. Объёмов нет, рынок мёртвый... 🥱",
                "Затишье перед бурей, чую скоро вниз польёмся на новостях 📉",
            ])
            bull_text = random.choice([
                "Идёт накопление позиции институционалами. Скоро выстрелим вверх! 📈",
                "Хорошая возможность докупить по спокойной цене без гэпов 🧘‍♂️",
            ])

        return [
            PulseComment(author="Паникёр_Василий", avatar="🐻", sentiment="bearish", text=bear_text),
            PulseComment(author="Ракета_Ходлер", avatar="🚀", sentiment="bullish", text=bull_text),
        ]

    def ask_mentor(
        self,
        question: str,
        scenario_name: str,
        scenario_sector: str,
        step: int,
        candle_data: Dict[str, Any],
        portfolio_status: Dict[str, Any],
    ) -> str:
        """
        Интерактивный вопрос AI-аналитику перед совершением хода.
        Отвечает кратко (2-3 предложения), не раскрывая реальный тикер и год.
        """
        if self.is_online and self.client is not None:
            try:
                system_prompt = (
                    "Ты — старший биржевой аналитик и финансовый консультант Т-Инвестиций. "
                    "Игрок находится внутри торговой сессии и задает тебе оперативный вопрос перед принятием решения (Купить, Продать, Держать). "
                    "Твоя задача — дать четкий, профессиональный и лаконичный ответ (2-3 предложения), опираясь на текущую свечу и новостной фон. "
                    "СТРОГИЕ ПРАВИЛА:\n"
                    f"1. Ни в коем случае НЕ называй реальный тикер, компанию или год. Актив называется исключительно «{scenario_name}».\n"
                    "2. Не давай категоричных рекомендаций типа 'срочно покупай на всё', объясняй логику рынка, уровни риска и управление кэшем.\n"
                    "3. Тон: доброжелательный, спокойный, экспертный в стиле Т-Банка."
                )

                user_content = (
                    f"Актив: {scenario_name} ({scenario_sector})\n"
                    f"Текущий день: #{step + 1}\n"
                    f"Цена закрытия: {candle_data.get('close', 0.0):,.2f} ₽ (изменение за день: {candle_data.get('change_pct', 0.0):+.2f}%)\n"
                    f"Новостной контекст: {candle_data.get('news_hint', '')}\n"
                    f"Свободный кэш игрока: {portfolio_status.get('cash', 0.0):,.2f} ₽, акций: {portfolio_status.get('shares', 0)} шт.\n"
                    f"Текущий PnL портфеля: {portfolio_status.get('pnl_pct', 0.0):+.2f}%\n"
                    f"Вопрос игрока: \"{question}\""
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=220,
                    temperature=0.6,
                    timeout=6.0,
                )
                answer = response.choices[0].message.content.strip()
                if answer:
                    return answer
            except Exception as e:
                print(f"[AIMaster] Ошибка вызова ask_mentor через LLM: {e}")

        # Fallback ответ
        return self._ask_mentor_fallback(
            question=question,
            scenario_name=scenario_name,
            candle_data=candle_data,
            portfolio_status=portfolio_status,
        )

    def _ask_mentor_fallback(
        self,
        question: str,
        scenario_name: str,
        candle_data: Dict[str, Any],
        portfolio_status: Dict[str, Any],
    ) -> str:
        """Интеллектуальный офлайн-ответ аналитика по ключевым словам."""
        q = question.lower()
        change_pct = candle_data.get("change_pct", 0.0)
        news_hint = candle_data.get("news_hint", "Рыночная неопределенность")
        close_p = candle_data.get("close", 0.0)
        cash = portfolio_status.get("cash", 0.0)
        shares = portfolio_status.get("shares", 0)

        # 1. Вопросы о падении
        if any(w in q for w in ["пада", "слив", "минус", "почему вниз", "обвал", "дно"]):
            if change_pct < 0:
                return (
                    f"Котировки {scenario_name} снижаются ({change_pct:+.2f}%) на фоне события: «{news_hint}». "
                    "На рынке преобладает эмоциональная фиксация позиций толпой. "
                    "Не пытайтесь ловить падающий нож всем депозитом — оцените, какую просадку комфортно пересидеть."
                )
            else:
                return (
                    f"Сегодня бумага закрылась в плюсе ({change_pct:+.2f}%), но общая тревожность в стакане сохраняется. "
                    "Учитывайте, что локальные отскоки на падающих трендах часто бывают ложными."
                )

        # 2. Вопросы о росте / ракете
        if any(w in q for w in ["раст", "ракета", "хай", "почему вверх", "плюс", "лонг"]):
            return (
                f"Импульс вверх ({change_pct:+.2f}%) подпитывается реакцией на новостной фон: «{news_hint}». "
                "Если вы уже в позиции, разумно подумать о защите прибыли. "
                "Покупать же на самом пике зеленой свечи — классическая ловушка для новичков."
            )

        # 3. Вопросы об усреднении / покупке
        if any(w in q for w in ["усредн", "докуп", "купить", "брать", "вход"]):
            if cash < close_p:
                return f"У вас осталось всего {cash:,.2f} ₽ свободных средств, на покупку целой акции не хватает. В данный момент логичнее удерживать позицию или зафиксировать прибыль."
            if change_pct < -3.0:
                return (
                    f"Усреднение на просадках снижает среднюю цену входа, но резко увеличивает риск портфеля. "
                    f"Свободный кэш ({cash:,.0f} ₽) — это ваша подушка безопасности. Если решитесь войти, делайте это осторожно."
                )
            return (
                f"Текущая цена {close_p:,.2f} ₽. При покупке ориентируйтесь на общий рыночный тренд, а не сиюминутные эмоции. "
                "Всегда сохраняйте часть кэша на случай непредвиденных новостных гэпов."
            )

        # 4. Вопросы о продаже / фиксации
        if any(w in q for w in ["прода", "слива", "выход", "зафиксир", "сброс"]):
            if shares == 0:
                return "В вашем портфеле сейчас 0 акций — продавать нечего. Вы находитесь в 100% кэше и полностью защищены от просадки."
            if change_pct < -5.0:
                return (
                    f"Выход из позиции на дне свечи часто приводит к фиксации убытка на эмоциях. "
                    "Однако если риск кажется вам запредельным — душевное спокойствие инвестора всегда важнее сиюминутного процента."
                )
            return (
                f"У вас в портфеле {shares} шт. акций. Фиксация прибыли или переход в кэш — отличный способ запереть доходность "
                "перед потенциальным усилением волатильности."
            )

        # 5. Вопросы об удержании (HOLD)
        if any(w in q for w in ["держа", "холд", "ждать", "сидеть"]):
            return (
                f"Тактика выжидания при текущей ситуации («{news_hint}») позволяет избежать лишних импульсивных ошибок. "
                "Если фундаментал актива вас устраивает, пересидеть локальную турбулентность — классический выбор опытных инвесторов."
            )

        # Дефолтный экспертный ответ
        return (
            f"Текущая цена актива {scenario_name} — {close_p:,.2f} ₽ (динамика дня: {change_pct:+.2f}%). "
            f"Ключевой фактор дня: «{news_hint}». "
            f"У вас в распоряжении {cash:,.0f} ₽ свободных средств и {shares} акций. "
            "Действуйте исходя из собственного риск-профиля и не поддавайтесь всеобщему шуму в ленте «Пульса»."
        )

    def generate_final_review(self, summary: Dict[str, Any]) -> FinalReviewResponse:
        """Генерация итогового разбора полетов для завершения квеста."""
        if self.is_online and self.client is not None:
            try:
                system_prompt = (
                    "Ты — старший инвестиционный консультант Т-Банка. "
                    "Игрок только что завершил 10-дневный квест на исторических данных российского рынка. "
                    "Проанализируй его результат, профиль инвестора и сделки. "
                    "Дай воодушевляющий, профессиональный и честный вердикт с советом на будущее. "
                    "Отвечай строго в формате валидного JSON со следующей структурой:\n"
                    "{\n"
                    '  "verdict": "Развернутый вердикт (2-3 предложения)",\n'
                    '  "strengths": ["Сильная сторона 1", "Сильная сторона 2"],\n'
                    '  "mistakes": ["Точка роста 1", "Точка роста 2"],\n'
                    '  "recommendations": "Практический совет по управлению портфелем",\n'
                    '  "quote": "Вдохновляющая финансовая мудрость"\n'
                    "}"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(summary, ensure_ascii=False)},
                    ],
                    temperature=0.7,
                    timeout=10.0,
                )

                data = json.loads(response.choices[0].message.content)
                return FinalReviewResponse(
                    verdict=data.get("verdict", "Игра завершена с достойным результатом."),
                    strengths=data.get("strengths", ["Контроль риска", "Следование плану"]),
                    mistakes=data.get("mistakes", ["Тайминг входов"]),
                    recommendations=data.get("recommendations", "Диверсифицируйте портфель регулярными покупками."),
                    quote=data.get("quote", "Рынок платит за терпение и дисциплину."),
                )
            except Exception as e:
                print(f"[AIMaster] Ошибка вызова LLM для финального обзора: {e}")

        # Fallback финальный разбор
        return self._generate_fallback_final_review(summary)

    def _generate_fallback_final_review(self, summary: Dict[str, Any]) -> FinalReviewResponse:
        """Офлайн генерация финального вердикта."""
        pnl_pct = summary.get("pnl_pct", 0.0)
        bench = summary.get("benchmark_pnl_pct", 0.0)
        profile_title = summary.get("profile", {}).get("title", "Инвестор")
        real_name = summary.get("real_name", "акций")

        if pnl_pct > bench:
            verdict = (
                f"Великолепный результат! Вы завершили квест с доходностью {pnl_pct:+.2f}%, "
                f"опередив пассивную стратегию рынка на {pnl_pct - bench:+.2f}%. "
                f"Ваш архетип «{profile_title}» доказал свою эффективность на отрезке {real_name}."
            )
            strengths = [
                "Своевременный выход из риска перед падениями",
                "Высокая дисциплина управления кэшем",
            ]
            mistakes = [
                "Иногда осторожность мешала забрать максимальный импульс",
            ]
            recomms = (
                "Для закрепления успеха добавьте в реальный портфель автоматические инвесткопилки "
                "и облигационную подушку безопасности."
            )
            quote = "«Лучшая сделка — та, которая сохранила капитал и принесла душевное спокойствие.»"
        else:
            verdict = (
                f"Рынок преподнес серьезный урок высокой волатильности: ваш результат составил {pnl_pct:+.2f}% "
                f"против {bench:+.2f}% бенчмарка. Исторический отрезок {real_name} проверил на прочность ваши нервы."
            )
            strengths = [
                "Практический опыт прохождения настоящего рыночного шторма",
                "Готовность принимать решения под давлением паники в Пульсе",
            ]
            mistakes = [
                "Вход на локальных хаях или эмоциональные сделки",
                "Отсутствие защитных стоп-приказов",
            ]
            recomms = (
                "Используйте стратегию усреднения DCA (регулярные покупки равными долями) "
                "и не торгуйте на все деньги в один день."
            )
            quote = "«Опыт на бирже покупается за убытки, а мудрость — за умение делать выводы.»"

        return FinalReviewResponse(
            verdict=verdict,
            strengths=strengths,
            mistakes=mistakes,
            recommendations=recomms,
            quote=quote,
        )


if __name__ == "__main__":
    # Тест генератора
    master = AIMaster()
    print(f"Статус AIMaster: {master.get_status_label()}")

    mock_candle = {"close": 257.0, "change_pct": -1.45, "news_hint": "Дипломатические переговоры продолжаются."}
    event = master.generate_daily_event(
        scenario_name="«Зелёный Гигант»",
        scenario_sector="Банки",
        step=1,
        total_steps=10,
        candle_data=mock_candle,
        last_trade={"action": "BUY"},
        portfolio_pnl_pct=-1.46,
    )
    print("\n--- Сгенерированное событие дня ---")
    print(f"Заголовок: {event.headline}")
    print(f"Новость: {event.news_summary}")
    print(f"Ментор: {event.mentor_feedback}")
    for p in event.pulse_comments:
        print(f"[{p.avatar} {p.author}]: {p.text}")
