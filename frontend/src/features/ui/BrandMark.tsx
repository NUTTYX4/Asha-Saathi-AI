/** The first letter of ಆಶಾ in a Berry disc, with the bilingual name beside it. */
export function BrandMark({ size = "md" }: { size?: "md" | "lg" }) {
  const lg = size === "lg";
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        lang="kn"
        className={`grid shrink-0 place-items-center rounded-full bg-berry-600 font-bold text-white ${lg ? "size-16 text-4xl" : "size-10 text-2xl"}`}
      >
        ಆ
      </span>
      <span className="flex flex-col leading-none">
        <span lang="kn" className={`font-bold text-berry-700 ${lg ? "text-4xl" : "text-xl"}`}>
          ಆಶಾ ಸಾಥಿ
        </span>
        <span className={`font-extrabold text-fg-2 ${lg ? "mt-1 text-lg" : "text-xs"}`}>ASHA Saathi</span>
      </span>
    </span>
  );
}
