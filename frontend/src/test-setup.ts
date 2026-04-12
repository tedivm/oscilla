import "@testing-library/jest-dom";

function createStorageMock(): Storage {
  let store: Record<string, string> = {};

  return {
    get length() {
      return Object.keys(store).length;
    },
    clear(): void {
      store = {};
    },
    getItem(key: string): string | null {
      return key in store ? store[key] : null;
    },
    key(index: number): string | null {
      return Object.keys(store)[index] ?? null;
    },
    removeItem(key: string): void {
      delete store[key];
    },
    setItem(key: string, value: string): void {
      store[key] = String(value);
    },
  };
}

if (
  typeof globalThis.localStorage === "undefined" ||
  typeof globalThis.localStorage.getItem !== "function"
) {
  Object.defineProperty(globalThis, "localStorage", {
    value: createStorageMock(),
    writable: true,
  });
}

if (
  typeof globalThis.sessionStorage === "undefined" ||
  typeof globalThis.sessionStorage.getItem !== "function"
) {
  Object.defineProperty(globalThis, "sessionStorage", {
    value: createStorageMock(),
    writable: true,
  });
}
