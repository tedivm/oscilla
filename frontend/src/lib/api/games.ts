import { apiFetch } from "./client.js";
import type { GameRead } from "./types.js";

export async function listGames(): Promise<GameRead[]> {
  return apiFetch<GameRead[]>("/api/games");
}

export async function getGame(name: string): Promise<GameRead> {
  return apiFetch<GameRead>(`/games/${encodeURIComponent(name)}`);
}
