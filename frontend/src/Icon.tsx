/** Small, code-native line icons; no font-dependent emoji or copied brand marks. */
export function Icon({ name }: { name: "heart" | "clock" | "ticket" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {name === "heart" ? (
        <path d="M20 5c-2-2-5-1.5-8 1.5C9 3.5 6 3 4 5s-2 5 0 7l8 8 8-8c2-2 2-5 0-7Z" />
      ) : name === "clock" ? (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </>
      ) : (
        <>
          <path d="M4 5h16v5a2 2 0 0 0 0 4v5H4v-5a2 2 0 0 0 0-4Z" />
          <path d="M9 5v2m0 3v4m0 3v2" />
        </>
      )}
    </svg>
  );
}
