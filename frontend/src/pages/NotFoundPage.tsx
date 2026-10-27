import clsx from "clsx";
import { Link } from "react-router";
import { buttonClasses } from "../components/ui";

export function NotFoundPage() {
  return (
    <main className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="font-serif text-3xl font-semibold tracking-tighter text-ink">Page not found</h1>
      <p className="mt-3 text-ink-muted">There's nothing at this address.</p>
      <Link to="/" className={clsx(buttonClasses("secondary"), "mt-6")}>
        Back to my courses
      </Link>
    </main>
  );
}
