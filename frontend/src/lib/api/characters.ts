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
  return apiFetch<CharacterSummaryRead[]>(`/characters${query}`);
}

export async function createCharacter(
  gameName: string,
): Promise<CharacterSummaryRead> {
  return apiFetch<CharacterSummaryRead>("/characters", {
    method: "POST",
    body: JSON.stringify({ game_name: gameName }),
  });
}

export async function getCharacter(id: string): Promise<CharacterStateRead> {
  return apiFetch<CharacterStateRead>(`/characters/${encodeURIComponent(id)}`);
}

export async function deleteCharacter(id: string): Promise<void> {
  return apiFetch<void>(`/characters/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function renameCharacter(
  id: string,
  name: string,
): Promise<CharacterSummaryRead> {
  return apiFetch<CharacterSummaryRead>(
    `/characters/${encodeURIComponent(id)}`,
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
    `/characters/${encodeURIComponent(characterId)}/overworld`,
  );
}

export async function navigateLocation(
  characterId: string,
  locationRef: string,
): Promise<OverworldStateRead> {
  return apiFetch<OverworldStateRead>(
    `/characters/${encodeURIComponent(characterId)}/navigate`,
    {
      method: "POST",
      body: JSON.stringify({ location_ref: locationRef }),
    },
  );
}
