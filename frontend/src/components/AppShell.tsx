import { Moon, Plus, Sun } from "lucide-react";
import { Link, Outlet } from "react-router";
import { useConfig } from "../api/hooks";
import { useTheme } from "../lib/theme";
import { Logo } from "./Logo";
import { Badge, IconButton } from "./ui";

export function AppShell() {
  const config = useConfig();
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-3 px-4 sm:px-6">
          <Link to="/" aria-label="Marginalia home">
            <Logo />
          </Link>
          {config.data?.demo && (
            <span title="No model is configured: Marginalia is using its offline demo model. Set ANTHROPIC_API_KEY or OPENAI_API_KEY for real courses.">
              <Badge tone="warning">
                Demo<span className="hidden sm:inline"> mode</span>
              </Badge>
            </span>
          )}
          <nav className="ml-auto flex items-center gap-1 sm:gap-2">
            <Link
              to="/"
              className="hidden rounded-lg px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink sm:block"
            >
              My courses
            </Link>
            <Link
              to="/new"
              className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3 whitespace-nowrap text-sm font-medium text-accent-ink shadow-sm hover:bg-accent-hover"
            >
              <Plus className="size-4" aria-hidden />
              New<span className="hidden sm:inline"> course</span>
            </Link>
            <IconButton
              label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              onClick={toggleTheme}
            >
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </IconButton>
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
