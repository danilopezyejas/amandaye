export interface WeatherMeasurements {
  temperature_c: number | null;
  humidity_pct: number | null;
  pressure_hpa: number | null;
  wind_speed_kmh: number | null;
  wind_gust_kmh: number | null;
  wind_direction_deg: number | null;
  wind_direction_cardinal: string | null;
  rain_1h_mm: number | null;
  rain_rate_mmh: number | null;
  rain_detected: boolean | null;
  wind_direction_ambiguous?: boolean;
}

export interface Observation extends WeatherMeasurements {
  timestamp: string | null;
  age_minutes: number | null;
  stale: boolean;
  available: boolean;
  last_known?: boolean;
  refreshing?: boolean;
}

export interface CurrentConditions extends Observation {
  station_ids: string[];
  stations_available: number;
  fallback: 'stale_observations' | null;
}

export interface WeatherStation extends Observation {
  id: string;
  name: string;
  provider: string;
  location: string;
  source_url: string;
  access_method?: 'api' | 'public_page';
  error?: string;
}

export interface ForecastHour {
  timestamp: string;
  temperature_c: number | null;
  humidity_pct: number | null;
  precipitation_mm: number | null;
  precipitation_probability_pct: number | null;
  wind_speed_kmh: number | null;
  wind_gust_kmh: number | null;
  wind_direction_deg: number | null;
  wind_direction_cardinal: string | null;
  weather_code: number | null;
}

export interface ForecastDay {
  date: string;
  temperature_min_c: number | null;
  temperature_max_c: number | null;
  wind_speed_min_kmh: number | null;
  wind_speed_max_kmh: number | null;
  wind_gust_max_kmh: number | null;
  precipitation_probability_max_pct: number | null;
  precipitation_sum_mm: number | null;
  weather_code: number | null;
}

export interface ConditionsResponse {
  weather: {
    current: CurrentConditions;
    sources: WeatherStation[];
    comparison: {
      wind_difference_kmh: number | null;
      gust_difference_kmh: number | null;
      temperature_difference_c: number | null;
      pressure_difference_hpa: number | null;
      significant: boolean;
      differing_fields: string[];
    };
  };
  forecast: {
    available: boolean;
    provider: string;
    source_url: string;
    fetched_at: string | null;
    age_minutes: number | null;
    stale: boolean;
    last_known?: boolean;
    refreshing?: boolean;
    error?: string;
    hourly: ForecastHour[];
    daily: ForecastDay | null;
  };
  meta: {
    generated_at: string;
    stale_after_minutes: number;
    forecast_stale_after_seconds: number;
    refresh_interval_seconds: number;
  };
}
