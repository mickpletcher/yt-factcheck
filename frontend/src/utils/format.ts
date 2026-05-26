export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remaining = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
  }
  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

export function timestampUrl(youtubeUrl: string, seconds: number): string {
  if (!youtubeUrl) {
    return "#";
  }
  try {
    const url = new URL(youtubeUrl);
    url.searchParams.set("t", `${Math.floor(seconds)}s`);
    return url.toString();
  } catch {
    return youtubeUrl;
  }
}
