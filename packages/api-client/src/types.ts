import type { components } from "./generated/schema";

type Schemas = components["schemas"];

export type Freshness = Schemas["FreshnessStatus"];
export type DataQuality = Schemas["DataQuality"];
export type LocationKind = Schemas["LocationKind"];
export type QueryKind = Schemas["QueryKind"];

export type Location = Schemas["Location"];
export type SourceAttribution = Schemas["SourceAttribution"];
export type ResponseMetadata = Schemas["ResponseMetadata"];
export type LocationSearchResponse = Schemas["LocationSearchResponse"];
export type CurrentConditions = Schemas["CurrentConditions"];
export type ObservationStation = Schemas["ObservationStation"];
export type CurrentWeatherResponse = Schemas["CurrentWeatherResponse"];
export type HourlyPeriod = Schemas["HourlyPeriod"];
export type HourlyWeatherResponse = Schemas["HourlyWeatherResponse"];
export type DailyPeriod = Schemas["DailyPeriod"];
export type DailyWeatherResponse = Schemas["DailyWeatherResponse"];
export type OfficialAlert = Schemas["OfficialAlert"];
export type ActiveAlertsResponse = Schemas["ActiveAlertsResponse"];
export type SourceHealth = Schemas["SourceHealth"];
export type SourcesResponse = Schemas["SourcesResponse"];
