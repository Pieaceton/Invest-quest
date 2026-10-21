"""
data_loader.py — Модуль загрузки и кэширования исторических рыночных сценариев.

Функционал:
1. Загрузка готовых исторических сценариев из локального кэша (data/scenarios.json).
2. Автоматическая генерация качественного тестового датасета при первом запуске (работает без API-ключа).
3. Интеграция с Tinkoff Invest API (v2 SDK) для выгрузки свежих реальных свечей по токену.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
SCENARIOS_FILE = DATA_DIR / "scenarios.json"


@dataclass
class Candle:
    step: int
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    change_pct: float
    news_hint: str  # Реальный исторический контекст (для ИИ)


@dataclass
class Scenario:
    id: str
    disguised_name: str
    disguised_sector: str
    disguised_description: str
    real_ticker: str
    real_name: str
    real_period: str
    real_summary: str
    candles: List[Candle]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Scenario:
        candles = [Candle(**c) if isinstance(c, dict) else c for c in data["candles"]]
        return cls(
            id=data["id"],
            disguised_name=data["disguised_name"],
            disguised_sector=data["disguised_sector"],
            disguised_description=data["disguised_description"],
            real_ticker=data["real_ticker"],
            real_name=data["real_name"],
            real_period=data["real_period"],
            real_summary=data["real_summary"],
            candles=candles,
        )


DEFAULT_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "scenario_sber_storm_2022",
        "disguised_name": "«Зелёный Гигант»",
        "disguised_sector": "Банки и Финансы",
        "disguised_description": "Крупнейший финансовый конгломерат с миллионами клиентов. Вокруг нарастает геополитическое напряжение, а на бирже начинается паника.",
        "real_ticker": "SBER",
        "real_name": "Сбербанк",
        "real_period": "11 февраля — 25 февраля 2022 года",
        "real_summary": "Две недели перед масштабным кризисом 2022 года. Исторический обвал котировок, экстренное повышение ставки ЦБ и беспрецедентный стресс-тест для инвесторов.",
        "candles": [
            {
                "step": 0,
                "date": "2022-02-11",
                "open": 264.5,
                "high": 268.0,
                "low": 258.1,
                "close": 260.8,
                "volume": 42000000,
                "change_pct": -1.4,
                "news_hint": "Пятничная фиксация прибыли на фоне тревожных заголовков зарубежных СМИ.",
            },
            {
                "step": 1,
                "date": "2022-02-14",
                "open": 253.0,
                "high": 259.5,
                "low": 248.0,
                "close": 257.0,
                "volume": 68000000,
                "change_pct": -1.45,
                "news_hint": "Встречи дипломатов дали слабую надежду, рынок пытается нащупать дно.",
            },
            {
                "step": 2,
                "date": "2022-02-15",
                "open": 260.0,
                "high": 272.5,
                "low": 258.8,
                "close": 270.2,
                "volume": 85000000,
                "change_pct": 5.14,
                "news_hint": "Заявления об отводе войск с учений вызывают мощный технический отскок.",
            },
            {
                "step": 3,
                "date": "2022-02-16",
                "open": 269.0,
                "high": 274.0,
                "low": 264.5,
                "close": 266.3,
                "volume": 53000000,
                "change_pct": -1.44,
                "news_hint": "Эйфория угасает, западные аналитики выражают сомнения в деэскалации.",
            },
            {
                "step": 4,
                "date": "2022-02-17",
                "open": 262.0,
                "high": 265.0,
                "low": 250.2,
                "close": 252.8,
                "volume": 74000000,
                "change_pct": -5.07,
                "news_hint": "Сообщения об обострении ситуации в Донбассе провоцируют волну распродаж.",
            },
            {
                "step": 5,
                "date": "2022-02-18",
                "open": 251.0,
                "high": 256.0,
                "low": 239.0,
                "close": 243.5,
                "volume": 91000000,
                "change_pct": -3.68,
                "news_hint": "Эвакуация населения и нарастание паники перед выходными днями.",
            },
            {
                "step": 6,
                "date": "2022-02-21",
                "open": 240.0,
                "high": 242.0,
                "low": 205.0,
                "close": 209.0,
                "volume": 185000000,
                "change_pct": -14.17,
                "news_hint": "Внеочередное заседание Совбеза РФ и признание ДНР/ЛНР. Обвал индекса Мосбиржи.",
            },
            {
                "step": 7,
                "date": "2022-02-22",
                "open": 195.0,
                "high": 218.0,
                "low": 190.0,
                "close": 208.5,
                "volume": 140000000,
                "change_pct": -0.24,
                "news_hint": "Высокая волатильность: маржин-коллы розничных инвесторов сменяются спекулятивным выкупом просадки.",
            },
            {
                "step": 8,
                "date": "2022-02-24",
                "open": 160.0,
                "high": 170.0,
                "low": 89.6,
                "close": 131.1,
                "volume": 290000000,
                "change_pct": -37.12,
                "news_hint": "Начало СВО. Исторический «чёрный четверг» российского фондового рынка, паника и обнуление маржинальных счетов.",
            },
            {
                "step": 9,
                "date": "2022-02-25",
                "open": 135.0,
                "high": 145.0,
                "low": 120.0,
                "close": 128.5,
                "volume": 120000000,
                "change_pct": -1.98,
                "news_hint": "Последний день торгов перед почти месячной приостановкой работы биржи ЦБ РФ.",
            },
        ],
    },
    {
        "id": "scenario_plzl_rally_2020",
        "disguised_name": "«Золотой Щит»",
        "disguised_sector": "Металлы и Добыча",
        "disguised_description": "Ведущий золотодобытчик. Мир охвачен страхом неизвестной пандемии, центробанки включают печатные станки, а инвесторы ищут тихую гавань.",
        "real_ticker": "PLZL",
        "real_name": "Полюс Золото",
        "real_period": "18 марта — 31 марта 2020 года",
        "real_summary": "Коронакризис весны 2020 года. Пока весь мировой рынок рушился в локдаунах, золото и акции золотодобытчиков показали взрывной взлёт защитного актива.",
        "candles": [
            {
                "step": 0,
                "date": "2020-03-18",
                "open": 9850.0,
                "high": 10200.0,
                "low": 9650.0,
                "close": 10050.0,
                "volume": 18000,
                "change_pct": 2.03,
                "news_hint": "Панические продажи на глобальных рынках, доллар растет, золото тестирует поддержку.",
            },
            {
                "step": 1,
                "date": "2020-03-19",
                "open": 10100.0,
                "high": 10550.0,
                "low": 9980.0,
                "close": 10450.0,
                "volume": 22000,
                "change_pct": 3.98,
                "news_hint": "Инвесторы начинают скупать акции золотодобытчиков для хеджирования девальвации рубля.",
            },
            {
                "step": 2,
                "date": "2020-03-20",
                "open": 10500.0,
                "high": 11000.0,
                "low": 10400.0,
                "close": 10890.0,
                "volume": 29000,
                "change_pct": 4.21,
                "news_hint": "ФРС США анонсирует рекордную программу количественного смягчения (QE).",
            },
            {
                "step": 3,
                "date": "2020-03-23",
                "open": 10900.0,
                "high": 11350.0,
                "low": 10800.0,
                "close": 11200.0,
                "volume": 31000,
                "change_pct": 2.85,
                "news_hint": "Мировые котировки золота демонстрируют максимальный дневной рост за 11 лет.",
            },
            {
                "step": 4,
                "date": "2020-03-24",
                "open": 11300.0,
                "high": 11900.0,
                "low": 11250.0,
                "close": 11800.0,
                "volume": 35000,
                "change_pct": 5.36,
                "news_hint": "Аналитики инвестдомов массово повышают целевые цены по сектору золотодобычи.",
            },
            {
                "step": 5,
                "date": "2020-03-25",
                "open": 11850.0,
                "high": 12100.0,
                "low": 11600.0,
                "close": 11750.0,
                "volume": 26000,
                "change_pct": -0.42,
                "news_hint": "Техническая передышка и фиксация быстрой прибыли внутри дня.",
            },
            {
                "step": 6,
                "date": "2020-03-26",
                "open": 11700.0,
                "high": 12250.0,
                "low": 11680.0,
                "close": 12150.0,
                "volume": 28000,
                "change_pct": 3.4,
                "news_hint": "Рост цен на драгметаллы продолжается, локальные инвесторы переводят сбережения в защитный актив.",
            },
            {
                "step": 7,
                "date": "2020-03-27",
                "open": 12200.0,
                "high": 12600.0,
                "low": 12100.0,
                "close": 12500.0,
                "volume": 33000,
                "change_pct": 2.88,
                "news_hint": "Объявлена неделя нерабочих дней в РФ. Спрос на защитные активы бьет рекорды.",
            },
            {
                "step": 8,
                "date": "2020-03-30",
                "open": 12550.0,
                "high": 12900.0,
                "low": 12450.0,
                "close": 12700.0,
                "volume": 30000,
                "change_pct": 1.6,
                "news_hint": "Цены на золото стабильно выше $1600 за унцию, отчетность компании сулит сверхприбыли.",
            },
            {
                "step": 9,
                "date": "2020-03-31",
                "open": 12750.0,
                "high": 13300.0,
                "low": 12680.0,
                "close": 13150.0,
                "volume": 41000,
                "change_pct": 3.54,
                "news_hint": "Закрытие квартала на исторических максимумах. Ралли принесло более +30% за 10 дней.",
            },
        ],
    },
    {
        "id": "scenario_yndx_hype_2021",
        "disguised_name": "«Цифровой Поисковик»",
        "disguised_sector": "IT и Технологии",
        "disguised_description": "Флагман российской интернет-индустрии и искусственного интеллекта. Растущая экосистема, взрывной рост выручки и перегретые ожидания толпы.",
        "real_ticker": "YNDX",
        "real_name": "Яндекс",
        "real_period": "1 ноября — 15 ноября 2021 года",
        "real_summary": "Кульминация технологического бычьего рынка осени 2021 года. Рекордные исторические хаи, сменяющиеся неожиданной сменой настроений крупных фондов.",
        "candles": [
            {
                "step": 0,
                "date": "2021-11-01",
                "open": 5510.0,
                "high": 5640.0,
                "low": 5480.0,
                "close": 5620.0,
                "volume": 160000,
                "change_pct": 1.99,
                "news_hint": "Сильный отчет за 3 квартал: рост выручки во всех сегментах такси и e-commerce.",
            },
            {
                "step": 1,
                "date": "2021-11-02",
                "open": 5650.0,
                "high": 5820.0,
                "low": 5630.0,
                "close": 5790.0,
                "volume": 210000,
                "change_pct": 3.02,
                "news_hint": "Инвестбанки соревнуются в повышении таргетов до 7000 рублей.",
            },
            {
                "step": 2,
                "date": "2021-11-03",
                "open": 5800.0,
                "high": 5950.0,
                "low": 5770.0,
                "close": 5910.0,
                "volume": 250000,
                "change_pct": 2.07,
                "news_hint": "Акции пробивают очередной психологический рубеж на притоке розничных денег.",
            },
            {
                "step": 3,
                "date": "2021-11-04",
                "open": 5920.0,
                "high": 6050.0,
                "low": 5890.0,
                "close": 6010.0,
                "volume": 280000,
                "change_pct": 1.69,
                "news_hint": "Праздничный день, на тонком рынке цена достигает абсолютного рекорда в 6000+ ₽.",
            },
            {
                "step": 4,
                "date": "2021-11-08",
                "open": 6040.0,
                "high": 6120.0,
                "low": 5980.0,
                "close": 6030.0,
                "volume": 230000,
                "change_pct": 0.33,
                "news_hint": "Пик эйфории. В соцсетях и пульсе новички спорят, как скоро акция дойдет до 10 000 ₽.",
            },
            {
                "step": 5,
                "date": "2021-11-09",
                "open": 6020.0,
                "high": 6040.0,
                "low": 5810.0,
                "close": 5840.0,
                "volume": 260000,
                "change_pct": -3.15,
                "news_hint": "Первые крупные институциональные продажи. Технические индикаторы сигналят о сильнейшей перекупленности.",
            },
            {
                "step": 6,
                "date": "2021-11-10",
                "open": 5820.0,
                "high": 5890.0,
                "low": 5690.0,
                "close": 5720.0,
                "volume": 240000,
                "change_pct": -2.05,
                "news_hint": "Данные по инфляции в США вызвали распродажу технологических акций по всему миру.",
            },
            {
                "step": 7,
                "date": "2021-11-11",
                "open": 5730.0,
                "high": 5820.0,
                "low": 5650.0,
                "close": 5700.0,
                "volume": 180000,
                "change_pct": -0.35,
                "news_hint": "Попытка стабилизации, блогеры советуют «выкупать просадку лидера рынка».",
            },
            {
                "step": 8,
                "date": "2021-11-12",
                "open": 5680.0,
                "high": 5720.0,
                "low": 5510.0,
                "close": 5550.0,
                "volume": 220000,
                "change_pct": -2.63,
                "news_hint": "Пробой уровня поддержки, стоп-лоссы розничных трейдеров ускоряют спад.",
            },
            {
                "step": 9,
                "date": "2021-11-15",
                "open": 5540.0,
                "high": 5580.0,
                "low": 5350.0,
                "close": 5380.0,
                "volume": 270000,
                "change_pct": -3.06,
                "news_hint": "Завершение двухнедельного цикла: весь рост начала месяца полностью стерт.",
            },
        ],
    },
]


class DataLoader:
    """Управление загрузкой сценариев: кэш JSON + Tinkoff Invest API."""

    def __init__(self, data_file: Path = SCENARIOS_FILE):
        self.data_file = Path(data_file)
        self._ensure_cache_exists()

    def _ensure_cache_exists(self) -> None:
        """Создает директорию data/ и scenarios.json с дефолтными данными, если файла нет."""
        if not self.data_file.exists():
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SCENARIOS, f, ensure_ascii=False, indent=2)

    def load_all_scenarios(self) -> List[Scenario]:
        """Возвращает список всех доступных сценариев."""
        self._ensure_cache_exists()
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return [Scenario.from_dict(item) for item in raw_data]
        except Exception:
            # Fallback на встроенные сценарии при любых сбоях чтения
            return [Scenario.from_dict(item) for item in DEFAULT_SCENARIOS]

    def get_scenario(self, scenario_id: Optional[str] = None) -> Scenario:
        """Получить сценарий по ID или первый доступный по умолчанию."""
        scenarios = self.load_all_scenarios()
        if not scenarios:
            raise ValueError("Нет доступных сценариев!")

        if scenario_id:
            for s in scenarios:
                if s.id == scenario_id:
                    return s

        return scenarios[0]

    def save_scenario(self, scenario: Scenario) -> None:
        """Сохраняет или обновляет сценарий в локальном JSON-кэше."""
        scenarios = self.load_all_scenarios()
        existing_idx = next((i for i, s in enumerate(scenarios) if s.id == scenario.id), None)

        if existing_idx is not None:
            scenarios[existing_idx] = scenario
        else:
            scenarios.append(scenario)

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in scenarios], f, ensure_ascii=False, indent=2)

    @staticmethod
    def fetch_from_tinkoff(
        token: str,
        figi: str,
        from_date: datetime,
        to_date: datetime,
        scenario_id: str,
        disguised_name: str,
        disguised_sector: str,
        disguised_description: str,
        real_ticker: str,
        real_name: str,
    ) -> Optional[Scenario]:
        """
        Выгрузка дневных свечей через официальный Tinkoff Investments SDK.
        Преобразует ответ в формат Scenario.
        Если SDK не установлен или произошла ошибка — вернет None.
        """
        try:
            from tinkoff.invest import CandleInterval, Client
            from tinkoff.invest.utils import quotation_to_decimal

            candles_list: List[Candle] = []

            with Client(token) as client:
                raw_candles = client.market_data.get_candles(
                    figi=figi,
                    from_=from_date,
                    to=to_date,
                    interval=CandleInterval.CANDLE_INTERVAL_DAY,
                ).candles

                prev_close: Optional[float] = None
                for step, c in enumerate(raw_candles):
                    o = float(quotation_to_decimal(c.open))
                    h = float(quotation_to_decimal(c.high))
                    l = float(quotation_to_decimal(c.low))
                    close_p = float(quotation_to_decimal(c.close))
                    v = int(c.volume)
                    date_str = c.time.strftime("%Y-%m-%d")

                    change_pct = round(((close_p - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
                    prev_close = close_p

                    candles_list.append(
                        Candle(
                            step=step,
                            date=date_str,
                            open=o,
                            high=h,
                            low=l,
                            close=close_p,
                            volume=v,
                            change_pct=change_pct,
                            news_hint=f"Динамика дня {change_pct:+.2f}%. Объём торгов: {v:,} шт.",
                        )
                    )

            if not candles_list:
                return None

            period_str = f"{candles_list[0].date} — {candles_list[-1].date}"

            return Scenario(
                id=scenario_id,
                disguised_name=disguised_name,
                disguised_sector=disguised_sector,
                disguised_description=disguised_description,
                real_ticker=real_ticker,
                real_name=real_name,
                real_period=period_str,
                real_summary=f"Исторический отрезок котировок {real_name} ({real_ticker}) за период {period_str}.",
                candles=candles_list,
            )

        except ImportError:
            print("Предупреждение: библиотека tinkoff-investments не установлена.")
            return None
        except Exception as e:
            print(f"Ошибка при выгрузке данных из Tinkoff Invest API: {e}")
            return None


if __name__ == "__main__":
    # Быстрый тест загрузчика
    loader = DataLoader()
    all_s = loader.load_all_scenarios()
    print(f"Успешно загружено сценариев: {len(all_s)}")
    for s in all_s:
        print(f" -> [{s.id}] {s.disguised_name} ({len(s.candles)} свечей)")
