"""
game_engine.py — Движок состояния игры "Инвест-Квест".

Управляет:
- Балансом (свободные рубли, количество акций, общая стоимость портфеля).
- Шагами игры (от 0 до конца сценария).
- Выполнением действий игрока ("BUY", "SELL_ALL", "HOLD").
- Историей сделок и расчетом PnL (в рублях и процентах) относительно бенчмарка.
- Определением профиля инвестора по итогам сессии.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from data_loader import Candle, Scenario


@dataclass
class TradeRecord:
    step: int
    action: str  # "BUY", "SELL_ALL", "HOLD"
    price: float
    shares_delta: int
    shares_total: int
    cash_after: float
    portfolio_value: float
    pnl_rub: float
    pnl_pct: float
    comment: str = ""


@dataclass
class InvestorProfile:
    title: str
    badge: str
    description: str
    characteristics: List[str]


class GameEngine:
    """Класс состояния и логики инвестиционного квеста."""

    INITIAL_BALANCE: float = 100_000.0

    def __init__(self, scenario: Scenario, initial_balance: float = INITIAL_BALANCE):
        self.scenario = scenario
        self.initial_balance = float(initial_balance)
        self.cash: float = float(initial_balance)
        self.shares: int = 0
        self.current_step: int = 0
        self.is_game_over: bool = False
        self.trade_history: List[TradeRecord] = []
        self.snapshots: List[Dict[str, Any]] = []

        # Фиксируем начальный снимок
        self._record_snapshot(action="START", comment="Старт квеста")

    @property
    def total_steps(self) -> int:
        return len(self.scenario.candles)

    @property
    def current_candle(self) -> Candle:
        """Текущая открытая свеча."""
        idx = min(self.current_step, self.total_steps - 1)
        return self.scenario.candles[idx]

    @property
    def current_price(self) -> float:
        return self.current_candle.close

    @property
    def candles_revealed(self) -> List[Candle]:
        """Все свечи, доступные игроку на данный момент."""
        return self.scenario.candles[: self.current_step + 1]

    @property
    def total_value(self) -> float:
        """Текущая суммарная стоимость портфеля (кэш + акции по текущей цене)."""
        return round(self.cash + (self.shares * self.current_price), 2)

    @property
    def pnl_rub(self) -> float:
        """Абсолютный финансовый результат в рублях."""
        return round(self.total_value - self.initial_balance, 2)

    @property
    def pnl_pct(self) -> float:
        """Доходность в процентах от первоначального депозита."""
        return round((self.pnl_rub / self.initial_balance) * 100, 2)

    @property
    def benchmark_pnl_pct(self) -> float:
        """
        Доходность стратегии «Купи и держи» (Buy & Hold):
        покупка на все деньги на шаге 0 и удержание до текущего шага.
        """
        start_price = self.scenario.candles[0].close
        if start_price <= 0:
            return 0.0
        return round(((self.current_price - start_price) / start_price) * 100, 2)

    @property
    def can_buy(self) -> bool:
        """Может ли игрок купить хотя бы одну акцию."""
        return self.cash >= self.current_price and not self.is_game_over

    @property
    def can_sell(self) -> bool:
        """Есть ли в портфеле акции для продажи."""
        return self.shares > 0 and not self.is_game_over

    def execute_action(self, action: str) -> TradeRecord:
        """
        Выполнить действие игрока ("BUY", "SELL_ALL", "HOLD")
        на текущем шаге по цене закрытия текущей свечи, после чего перейти к следующему шагу.
        """
        if self.is_game_over:
            raise RuntimeError("Игра уже завершена. Начните новую игру.")

        action = action.upper().strip()
        price = self.current_price
        shares_delta = 0
        comment = ""

        if action == "BUY":
            # Покупка на все доступные свободные средства
            max_shares = int(self.cash // price)
            if max_shares > 0:
                cost = max_shares * price
                self.cash -= cost
                self.shares += max_shares
                shares_delta = max_shares
                comment = f"Куплено {max_shares} шт. по цене {price:,.2f} ₽"
            else:
                comment = "Недостаточно средств для покупки даже 1 акции"

        elif action == "SELL_ALL":
            # Продажа 100% имеющихся акций
            if self.shares > 0:
                revenue = self.shares * price
                shares_delta = -self.shares
                comment = f"Продано {self.shares} шт. по цене {price:,.2f} ₽"
                self.cash += revenue
                self.shares = 0
            else:
                comment = "Нет акций для продажи"

        elif action == "HOLD":
            comment = f"Позиция сохранена: {self.shares} шт. акций, {self.cash:,.2f} ₽ кэша"

        else:
            raise ValueError(f"Неизвестное действие: {action}. Ожидалось: BUY, SELL_ALL, HOLD.")

        # Фиксируем сделку
        record = TradeRecord(
            step=self.current_step,
            action=action,
            price=price,
            shares_delta=shares_delta,
            shares_total=self.shares,
            cash_after=round(self.cash, 2),
            portfolio_value=self.total_value,
            pnl_rub=self.pnl_rub,
            pnl_pct=self.pnl_pct,
            comment=comment,
        )
        self.trade_history.append(record)
        self._record_snapshot(action=action, comment=comment)

        # Переход к следующему дню
        if self.current_step >= self.total_steps - 1:
            self.is_game_over = True
        else:
            self.current_step += 1

        return record

    def _record_snapshot(self, action: str, comment: str = "") -> None:
        """Сохранение контрольной точки для аналитики и графиков."""
        self.snapshots.append(
            {
                "step": self.current_step,
                "action": action,
                "price": self.current_price,
                "cash": round(self.cash, 2),
                "shares": self.shares,
                "total_value": self.total_value,
                "pnl_rub": self.pnl_rub,
                "pnl_pct": self.pnl_pct,
                "comment": comment,
            }
        )

    def get_summary(self) -> Dict[str, Any]:
        """Итоговый отчет по сессии для экрана завершения игры."""
        profile = self.get_investor_profile()
        return {
            "initial_balance": self.initial_balance,
            "final_value": self.total_value,
            "pnl_rub": self.pnl_rub,
            "pnl_pct": self.pnl_pct,
            "benchmark_pnl_pct": self.benchmark_pnl_pct,
            "alpha_pct": round(self.pnl_pct - self.benchmark_pnl_pct, 2),
            "trades_count": len([t for t in self.trade_history if t.action in ("BUY", "SELL_ALL")]),
            "profile": asdict(profile),
            "real_ticker": self.scenario.real_ticker,
            "real_name": self.scenario.real_name,
            "real_period": self.scenario.real_period,
            "real_summary": self.scenario.real_summary,
        }

    def get_investor_profile(self) -> InvestorProfile:
        """
        Анализ поведения игрока на основе совершенных сделок,
        динамики баланса и итогового финансового результата.
        """
        buys = sum(1 for t in self.trade_history if t.action == "BUY")
        sells = sum(1 for t in self.trade_history if t.action == "SELL_ALL")
        holds = sum(1 for t in self.trade_history if t.action == "HOLD")
        total_pnl = self.pnl_pct
        bench = self.benchmark_pnl_pct

        # Пассивный холдер / Алмазные руки
        if buys == 1 and sells == 0:
            return InvestorProfile(
                title="Алмазные Руки",
                badge="💎",
                description="Вы вошли в актив и хладнокровно держали позицию сквозь любые штормы и волатильность.",
                characteristics=["Не поддается рыночной панике", "Классический Buy & Hold", "Стальные нервы"],
            )

        # Ни одной сделки (пересидел в кэше)
        if buys == 0:
            return InvestorProfile(
                title="Осторожный Хранитель",
                badge="🛡️",
                description="Вы предпочли остаться в 100% кэше, не рискнув ни одним рублем в период турбулентности.",
                characteristics=["Нулевая толерантность к риску", "Капитал в полной безопасности", "Упущенная выгода"],
            )

        # Трейдер с высокой активностью
        if (buys + sells) >= 4:
            if total_pnl > bench:
                return InvestorProfile(
                    title="Снайпер Волатильности",
                    badge="🎯",
                    description="Вы виртуозно ловили импульсы, вовремя фиксировали прибыль и обогнали рынок активной торговлей.",
                    characteristics=["Высокая скорость реакции", "Понимание рыночных циклов", "Спекулятивный азарт"],
                )
            else:
                return InvestorProfile(
                    title="Импульсивный Скальпер",
                    badge="⚡",
                    description="Частые сделки и эмоциональные решения сожгли часть вашей потенциальной доходности.",
                    characteristics=["Склонность к овертрейдингу", "Торговля на эмоциях", "Высокая комиссионная нагрузка"],
                )

        # Паническая продажа на дне
        if sells > 0 and total_pnl < bench and total_pnl < -5.0:
            return InvestorProfile(
                title="Жертва Паники",
                badge="😱",
                description="Страх дальнейших потерь заставил вас сбросить актив на коррекции в самый неподходящий момент.",
                characteristics=["Уязвимость к негативному инфополю", "Фиксация убытков на дне", "Урок для риск-менеджмента"],
            )

        # Разумный инвестор
        if total_pnl >= 0:
            return InvestorProfile(
                title="Мудрый Стратег",
                badge="🦉",
                description="Вы действовали взвешенно, сохранили капитал и смогли извлечь прибыль из непростой рыночной фазы.",
                characteristics=["Дисциплинированный подход", "Баланс риска и доходности", "Аналитический склад ума"],
            )

        return InvestorProfile(
            title="Закалённый Практик",
            badge="🧭",
            description="Рынок преподнес непростой урок, но полученный практический опыт ценнее сиюминутной прибыли.",
            characteristics=["Боевое крещение рынком", "Готовность анализировать ошибки", "Основа будущих побед"],
        )


if __name__ == "__main__":
    # Быстрый тест движка игры
    from data_loader import DataLoader

    loader = DataLoader()
    scenario = loader.get_scenario("scenario_sber_storm_2022")
    engine = GameEngine(scenario)

    print(f"--- Тест сценария: {scenario.disguised_name} ---")
    print(f"Старт: кэш = {engine.cash:,.2f} ₽, акции = {engine.shares}")

    # Имитируем шаги
    engine.execute_action("BUY")
    print(f"Шаг 0 (BUY): кэш = {engine.cash:,.2f} ₽, акции = {engine.shares}, баланс = {engine.total_value:,.2f} ₽")

    while not engine.is_game_over:
        rec = engine.execute_action("HOLD")
        print(f"Шаг {rec.step} (HOLD): цена = {rec.price:.2f} ₽, баланс = {rec.portfolio_value:,.2f} ₽, PnL = {rec.pnl_pct:+.2f}%")

    summary = engine.get_summary()
    print("\n--- Финал игры ---")
    print(f"Реальный тикер: {summary['real_ticker']} ({summary['real_name']})")
    print(f"Итоговый PnL: {summary['pnl_pct']:+.2f}% ({summary['pnl_rub']:+,.2f} ₽)")
    print(f"Бенчмарк: {summary['benchmark_pnl_pct']:+.2f}%")
    print(f"Профиль: {summary['profile']['badge']} {summary['profile']['title']}")
