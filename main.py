from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import swisseph as swe


SIGNS_RU = [
    "Овен",
    "Телец",
    "Близнецы",
    "Рак",
    "Лев",
    "Дева",
    "Весы",
    "Скорпион",
    "Стрелец",
    "Козерог",
    "Водолей",
    "Рыбы",
]


class NatalRequest(BaseModel):
    name: Optional[str] = Field(default=None)
    birth_date: str = Field(..., description="Дата рождения в формате YYYY-MM-DD")
    birth_time: Optional[str] = Field(
        default=None, description="Время рождения в формате HH:MM (локальное)"
    )
    time_unknown: bool = False
    latitude: float = Field(..., description="Широта места рождения")
    longitude: float = Field(..., description="Долгота места рождения")
    tz_offset_hours: float = Field(
        0,
        description="Смещение часового пояса относительно UTC на момент рождения, например 3 для UTC+3",
    )


class PlanetPosition(BaseModel):
    name: str
    sign: str
    longitude: float


class NatalResponse(BaseModel):
    sun_sign: str
    moon_sign: str
    ascendant_sign: str
    ascendant_degree: float
    planets: list[PlanetPosition]


app = FastAPI(title="Natal Chart API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_local_datetime(
    birth_date: str, birth_time: Optional[str], tz_offset_hours: float
) -> datetime:
    year, month, day = map(int, birth_date.split("-"))
    if birth_time:
        hours, minutes = map(int, birth_time.split(":"))
    else:
        hours, minutes = 12, 0

    offset = timezone(timedelta(hours=tz_offset_hours))
    return datetime(year, month, day, hours, minutes, tzinfo=offset)


def _julday_utc(dt_local: datetime) -> float:
    dt_utc = dt_local.astimezone(timezone.utc)
    year = dt_utc.year
    month = dt_utc.month
    day = dt_utc.day
    hour_decimal = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    return swe.julday(year, month, day, hour_decimal, swe.GREG_CAL)


def _sign_from_longitude(lon: float) -> str:
    index = int(lon // 30) % 12
    return SIGNS_RU[index]


@app.post("/api/natal-chart/calculate", response_model=NatalResponse)
def calculate_natal_chart(payload: NatalRequest) -> NatalResponse:
    dt_local = _parse_local_datetime(
        payload.birth_date, payload.birth_time, payload.tz_offset_hours
    )
    jd_ut = _julday_utc(dt_local)

    swe.set_ephe_path(".")

    sun_lon, *_ = swe.calc_ut(jd_ut, swe.SUN)
    moon_lon, *_ = swe.calc_ut(jd_ut, swe.MOON)

    houses, ascmc = swe.houses(jd_ut, payload.latitude, payload.longitude, b"P")
    asc_deg = float(ascmc[0])

    planets = [
        PlanetPosition(name="Солнце", sign=_sign_from_longitude(sun_lon), longitude=sun_lon),
        PlanetPosition(name="Луна", sign=_sign_from_longitude(moon_lon), longitude=moon_lon),
    ]

    return NatalResponse(
        sun_sign=_sign_from_longitude(sun_lon),
        moon_sign=_sign_from_longitude(moon_lon),
        ascendant_sign=_sign_from_longitude(asc_deg),
        ascendant_degree=asc_deg,
        planets=planets,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

