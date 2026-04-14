import { apiFetch } from "./client.js";
import type {
  CharacterStateRead,
  CharacterSummaryRead,
  OverworldStateRead,
} from "./types.js";

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

export async function navigateLocation(
  characterId: string,
  locationRef: string,
): Promise<OverworldStateRead> {
  return apiFetch<OverworldStateRead>(
    `/api/characters/${encodeURIComponent(characterId)}/navigate`,
    {
      method: "POST",
      body: JSON.stringify({ location_ref: locationRef }),
    },
  );
}
