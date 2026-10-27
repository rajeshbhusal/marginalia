import { Route, Routes } from "react-router";
import { AppShell } from "./components/AppShell";
import { CoursePage } from "./pages/CoursePage";
import { HomePage } from "./pages/HomePage";
import { NewCoursePage } from "./pages/NewCoursePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReaderPage } from "./pages/ReaderPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="new" element={<NewCoursePage />} />
        <Route path="courses/:courseId" element={<CoursePage />} />
        <Route path="courses/:courseId/learn/:sectionId" element={<ReaderPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
