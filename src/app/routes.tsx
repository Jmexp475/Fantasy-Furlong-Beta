import { createBrowserRouter } from "react-router-dom";
import { Layout } from "./components/Layout";
import Home from "./pages/Home";
import RacePicks from "./pages/RacePicks";
import Racecard from "./pages/Racecard";
import Results from "./pages/Results";
import Standings from "./pages/Standings";
import OpponentView from "./pages/OpponentView";
import More from "./pages/More";
import Admin from "./pages/Admin";
import Join from "./pages/Join";

export const router = createBrowserRouter([
  { path: "/join", Component: Join },
  { path: "/", Component: Layout, children: [
    { index: true, Component: Home },
    { path: "picks", Component: RacePicks },
    { path: "racecard", Component: Racecard },
    { path: "results", Component: Results },
    { path: "standings", Component: Standings },
    { path: "opponent", Component: OpponentView },
    { path: "more", Component: More },
    { path: "admin", Component: Admin }
  ] }
]);
