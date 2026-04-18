import { ApiError, apiFetch } from "./client.js";
import type {
  CharacterStateRead,
  CharacterSummaryRead,
  OverworldStateRead,
} from "./types.js";

/** Structured detail body sent when a character has an active adventure lock. */
export interface ActiveAdventureConflict {
  code: "active_adventure";
  character_id: string;
}

/**
 * Returns true when `err` is a 409 ApiError whose detail body indicates
 * an active adventure lock — use to redirect the user to the play screen.
 */
export function isActiveAdventureConflict(
  err: unknown,
): err is ApiError & { body: { detail: ActiveAdventureConflict } } {
  if (!(err instanceof ApiError) || err.status !== 409) return false;
  const body = err.body as Record<string, unknown> | null;
  return (
    body !== null &&
    typeof body === "object" &&
    "detail" in body &&
    typeof (body as Record<string, unknown>)["detail"] === "object" &&
    (body as Record<string, Record<string, unknown>>)["detail"]?.["code"] ===
      "active_adventure"
  );
}

export async function listCharacters(
  gameName?: string,
): Promise<CharacterSummaryRead[]> {
  const query = gameName ? `?game=${encodeURIComponent(gameName)}` : "";
  return apiFetch<CharacterSummaryRead[]>(`/api/characters${query}`);
}

export async function createCharacter(
  gameName: string,
): Promise<CharacterSummaryRead> {
  return apiFetch<CharacterSummaryRead>("/api/characters", {
    method: "POST",
    body: JSON.stringify({ game_name: gameName }),
  });
}

export async function getCharacter(id: string): Promise<CharacterStateRead> {
  return apiFetch<CharacterStateRead>(
    `/api/characters/${encodeURIComponent(id)}`,
  );
}

export async function deleteCharacter(id: string): Promise<void> {
  return apiFetch<void>(`/api/characters/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function renameCharacter(
  id: string,
  name: string,
): Promise<CharacterSummaryRead> {
  return apiFetch<CharacterSummaryRead>(
    `/api/characters/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ name }),
    },
  );
}

export async function getOverworld(
  characterId: string,
): Promise<OverworldStateRead> {
  return apiFetch<OverworldStateRead>(
    `/api/characters/${encodeURIComponent(characterId)}/overworld`,
  );
}
