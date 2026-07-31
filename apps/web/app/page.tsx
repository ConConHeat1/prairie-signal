import { WeatherDashboard } from "../components/weather-dashboard";

export default function HomePage() {
  return (
    <WeatherDashboard
      siteName={process.env.NEXT_PUBLIC_APP_NAME ?? "Prairie Signal"}
    />
  );
}
