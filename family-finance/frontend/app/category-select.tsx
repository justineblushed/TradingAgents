import { Category, groupedCategorySections } from "@/lib/api";

/** The set of <optgroup>s for a category picker, in the same order the
 *  Categories page itself renders: expense categories grouped the way that
 *  page groups them, then Income, then Transfer — instead of the flat A-Z
 *  list /categories returns on its own. Used by every category <select> in
 *  the app so they can't drift into their own separate ordering. */
export function CategoryOptions({ categories }: { categories: Category[] }) {
  return (
    <>
      {groupedCategorySections(categories).map((section) => (
        <optgroup key={section.label} label={section.label}>
          {section.categories.map((c) => (
            <option key={c.id} value={c.name}>
              {c.emoji ? `${c.emoji} ${c.name}` : c.name}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}
