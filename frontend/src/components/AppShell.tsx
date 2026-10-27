import clsx from "clsx";
import { Moon, Plus, Sun } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router";
import { useConfig } from "../api/hooks";
import { useTheme } from "../lib/theme";
import { Logo } from "./Logo";
import { Badge, buttonClasses, IconButton } from "./ui";

export function AppShell() {
  const config = useConfig();
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-line bg-canvas">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-2 px-4 sm:gap-3 sm:px-6">
          <Link to="/" aria-label="Marginalia home" className="-ml-1 rounded-lg p-1">
            <Logo />
          </Link>
          {config.data?.demo && (
            <span title="No model is configured: Marginalia is using its offline demo model. Set ANTHROPIC_API_KEY or OPENAI_API_KEY for real courses.">
              <Badge tone="warning">
                Demo<span className="hidden sm:inline"> mode</span>
              </Badge>
            </span>
          )}
          <nav aria-label="Main" className="ml-auto flex items-center gap-1 sm:gap-2">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                clsx(
                  "hidden h-8 items-center rounded-lg px-3 text-sm font-medium transition-colors sm:inline-flex",
                  isActive ? "bg-sunken text-ink" : "text-ink-muted hover:bg-surface-hover hover:text-ink",
                )
              }
            >
              My courses
            </NavLink>
            <Link to="/new" className={buttonClasses("secondary", "sm")}>
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
