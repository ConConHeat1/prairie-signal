export interface paths {
    "/api/v1/alerts/active": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Active Alerts */
        get: operations["active_alerts_api_v1_alerts_active_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/location/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search Locations */
        get: operations["search_locations_api_v1_location_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Readiness */
        get: operations["readiness_api_v1_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sources */
        get: operations["sources_api_v1_sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/weather/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current Weather */
        get: operations["current_weather_api_v1_weather_current_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/weather/daily": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Daily Weather */
        get: operations["daily_weather_api_v1_weather_daily_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/weather/hourly": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Hourly Weather */
        get: operations["hourly_weather_api_v1_weather_hourly_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActiveAlertsResponse */
        ActiveAlertsResponse: {
            /** Alerts */
            alerts: components["schemas"]["OfficialAlert"][];
            location: components["schemas"]["Location"];
            meta: components["schemas"]["ResponseMetadata"];
            status: components["schemas"]["AlertFeedStatus"];
        };
        /**
         * AlertFeedStatus
         * @enum {string}
         */
        AlertFeedStatus: "available" | "unavailable";
        /** CurrentConditions */
        CurrentConditions: {
            /** Apparent Temperature C */
            apparent_temperature_c: number | null;
            /** Dewpoint C */
            dewpoint_c: number | null;
            /** Icon Url */
            icon_url: string | null;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Pressure Hpa */
            pressure_hpa?: number | null;
            /** Relative Humidity Pct */
            relative_humidity_pct?: number | null;
            /** Temperature C */
            temperature_c: number | null;
            /** Text Description */
            text_description: string | null;
            /** Visibility Km */
            visibility_km?: number | null;
            /** Wind Direction Deg */
            wind_direction_deg?: number | null;
            /** Wind Gust Kph */
            wind_gust_kph?: number | null;
            /** Wind Speed Kph */
            wind_speed_kph?: number | null;
        };
        /** CurrentWeatherResponse */
        CurrentWeatherResponse: {
            current: components["schemas"]["CurrentConditions"];
            location: components["schemas"]["Location"];
            meta: components["schemas"]["ResponseMetadata"];
            station: components["schemas"]["ObservationStation"];
        };
        /** DailyPeriod */
        DailyPeriod: {
            /** Detailed Forecast */
            detailed_forecast: string;
            /**
             * End Time
             * Format: date-time
             */
            end_time: string;
            /** Icon Url */
            icon_url: string | null;
            /** Is Daytime */
            is_daytime: boolean;
            /** Name */
            name: string;
            /** Number */
            number: number;
            /** Probability Of Precipitation Pct */
            probability_of_precipitation_pct?: number | null;
            /** Short Forecast */
            short_forecast: string;
            /**
             * Start Time
             * Format: date-time
             */
            start_time: string;
            /** Temperature C */
            temperature_c: number | null;
            /** Wind Direction */
            wind_direction: string | null;
            /** Wind Speed Max Kph */
            wind_speed_max_kph?: number | null;
            /** Wind Speed Min Kph */
            wind_speed_min_kph?: number | null;
        };
        /** DailyWeatherResponse */
        DailyWeatherResponse: {
            location: components["schemas"]["Location"];
            meta: components["schemas"]["ResponseMetadata"];
            /** Periods */
            periods: components["schemas"]["DailyPeriod"][];
        };
        /**
         * DataQuality
         * @enum {string}
         */
        DataQuality: "verified" | "partial" | "unavailable";
        /**
         * FreshnessStatus
         * @enum {string}
         */
        FreshnessStatus: "fresh" | "delayed" | "stale" | "unavailable";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /** Service */
            service: string;
            /**
             * Status
             * @constant
             */
            status: "ok";
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
            /** Version */
            version: string;
        };
        /** HourlyPeriod */
        HourlyPeriod: {
            /** Dewpoint C */
            dewpoint_c: number | null;
            /**
             * End Time
             * Format: date-time
             */
            end_time: string;
            /** Icon Url */
            icon_url: string | null;
            /** Is Daytime */
            is_daytime: boolean;
            /** Probability Of Precipitation Pct */
            probability_of_precipitation_pct?: number | null;
            /** Relative Humidity Pct */
            relative_humidity_pct?: number | null;
            /** Short Forecast */
            short_forecast: string;
            /**
             * Start Time
             * Format: date-time
             */
            start_time: string;
            /** Temperature C */
            temperature_c: number | null;
            /** Wind Direction */
            wind_direction: string | null;
            /** Wind Direction Deg */
            wind_direction_deg?: number | null;
            /** Wind Gust Kph */
            wind_gust_kph?: number | null;
            /** Wind Speed Kph */
            wind_speed_kph?: number | null;
        };
        /** HourlyWeatherResponse */
        HourlyWeatherResponse: {
            location: components["schemas"]["Location"];
            meta: components["schemas"]["ResponseMetadata"];
            /** Periods */
            periods: components["schemas"]["HourlyPeriod"][];
        };
        /** Location */
        Location: {
            /**
             * Country
             * @default US
             * @constant
             */
            country: "US";
            /** Id */
            id: string;
            kind: components["schemas"]["LocationKind"];
            /** Label */
            label: string;
            /** Latitude */
            latitude: number;
            /** Longitude */
            longitude: number;
            /** Name */
            name: string;
            /** Region */
            region: string;
            /** Timezone */
            timezone: string;
        };
        /**
         * LocationKind
         * @enum {string}
         */
        LocationKind: "city" | "zcta" | "coordinate";
        /** LocationSearchResponse */
        LocationSearchResponse: {
            query_kind: components["schemas"]["QueryKind"];
            /** Region Limit Km */
            region_limit_km: number;
            /** Results */
            results: components["schemas"]["Location"][];
        };
        /** ObservationStation */
        ObservationStation: {
            /** Distance Km */
            distance_km: number;
            /** Id */
            id: string;
            /** Latitude */
            latitude: number;
            /** Longitude */
            longitude: number;
            /** Name */
            name: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
        };
        /** OfficialAlert */
        OfficialAlert: {
            /** Area Description */
            area_description: string;
            /** Certainty */
            certainty: string;
            /** Description */
            description: string;
            /**
             * Effective At
             * Format: date-time
             */
            effective_at: string;
            /** Ends At */
            ends_at: string | null;
            /** Event */
            event: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Geometry */
            geometry: {
                [key: string]: unknown;
            } | null;
            /** Headline */
            headline: string | null;
            /** Id */
            id: string;
            /** Instruction */
            instruction: string | null;
            /** Issuing Office */
            issuing_office: string | null;
            /** Message Type */
            message_type: string;
            /** Onset At */
            onset_at: string | null;
            /** Response */
            response: string | null;
            /** Revision Id */
            revision_id: string;
            /**
             * Sent At
             * Format: date-time
             */
            sent_at: string;
            /** Severity */
            severity: string;
            /** Status */
            status: string;
            /** Urgency */
            urgency: string;
        };
        /**
         * QueryKind
         * @enum {string}
         */
        QueryKind: "city" | "zip" | "coordinate";
        /** ReadinessCheck */
        ReadinessCheck: {
            /** Checks */
            checks: {
                [key: string]: boolean;
            };
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "not_ready";
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        /** ResponseMetadata */
        ResponseMetadata: {
            attribution?: components["schemas"]["SourceAttribution"];
            /** Confidence */
            confidence?: null;
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
            freshness: components["schemas"]["FreshnessStatus"];
            /**
             * From Cache
             * @default false
             */
            from_cache: boolean;
            /** Pipeline Version */
            pipeline_version: string;
            /**
             * Processed At
             * Format: date-time
             */
            processed_at: string;
            quality: components["schemas"]["DataQuality"];
            /** Source Time */
            source_time: string | null;
            /**
             * Stale Fallback
             * @default false
             */
            stale_fallback: boolean;
            /** Units */
            units: {
                [key: string]: string;
            };
            /** Valid From */
            valid_from: string | null;
            /** Valid To */
            valid_to: string | null;
            /** Warnings */
            warnings?: string[];
        };
        /** SourceAttribution */
        SourceAttribution: {
            /**
             * Name
             * @default National Weather Service
             */
            name: string;
            /**
             * Url
             * Format: uri
             * @default https://www.weather.gov/
             */
            url: string;
        };
        /** SourceHealth */
        SourceHealth: {
            /**
             * Circuit State
             * @enum {string}
             */
            circuit_state: "closed" | "open" | "half_open";
            /** Configured */
            configured: boolean;
            /** Consecutive Failures */
            consecutive_failures: number;
            /** Last Failure At */
            last_failure_at: string | null;
            /** Last Success At */
            last_success_at: string | null;
            /** Name */
            name: string;
        };
        /** SourcesResponse */
        SourcesResponse: {
            /** Sources */
            sources: components["schemas"]["SourceHealth"][];
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    active_alerts_api_v1_alerts_active_get: {
        parameters: {
            query: {
                latitude: number;
                longitude: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActiveAlertsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    search_locations_api_v1_location_search_get: {
        parameters: {
            query: {
                q: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocationSearchResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    readiness_api_v1_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadinessCheck"];
                };
            };
        };
    };
    sources_api_v1_sources_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourcesResponse"];
                };
            };
        };
    };
    current_weather_api_v1_weather_current_get: {
        parameters: {
            query: {
                latitude: number;
                longitude: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CurrentWeatherResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    daily_weather_api_v1_weather_daily_get: {
        parameters: {
            query: {
                latitude: number;
                longitude: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DailyWeatherResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    hourly_weather_api_v1_weather_hourly_get: {
        parameters: {
            query: {
                hours?: number;
                latitude: number;
                longitude: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HourlyWeatherResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
