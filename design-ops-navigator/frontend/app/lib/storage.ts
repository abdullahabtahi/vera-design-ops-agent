/**
 * UID-aware localStorage key helper.
 * Call initStorage(uid) after Firebase auth resolves.
 * All subsequent storageKey() calls are namespaced by that uid.
 */

let _uid: string | null = null;

export function initStorage(uid: string | null) {
  _uid = uid;
}

export function getStorageUid(): string | null {
  return _uid;
}

/**
 * Returns a namespaced localStorage key.
 * With uid:    "don.{uid}.{name}"
 * Without uid: "don.{name}"   ← backwards-compat fallback
 */
export function storageKey(name: string): string {
  return _uid ? `don.${_uid}.${name}` : `don.${name}`;
}
