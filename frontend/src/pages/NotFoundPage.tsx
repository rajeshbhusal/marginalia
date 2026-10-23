import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <main className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="font-serif text-3xl font-semibold">Page not found</h1>
      <p className="mt-3 text-ink-2">There's nothing at this address.</p>
      <Link to="/" className="mt-6 inline-block text-accent underline underline-offset-4">
        Back to your courses
      </Link>
    </main>
  );
}
