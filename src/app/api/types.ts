export type RaceStatus = "declared" | "off" | "result" | "abandoned";
export type FinishStatus = "finished" | "pulled_up" | "unseated" | "fell" | "refused" | "dnf";

export interface Runner {
  id: string;
  raceId: string;
  horseName: string;
  draw: number;
  jockey: string;
  trainer: string;
  owner: string;
  weight: string;
  officialRating: number;
  form: string;
  details: string;
  breeding: string;
  rawOdds: number;
  fairOdds: number;
  isNR: boolean;
  finishPosition?: number;
  finishStatus?: FinishStatus;
  lengths?: number;
  pointsWin: number;
  pointsPlace: number;
  pointsAwarded?: number;
  silkColors: string[];
  silkUrl?: string;
  sire?: string;
  dam?: string;
  quotes?: string[];
  quote?: string;
}

export interface Race {
  id: string;
  meetingId: string;
  dayIndex: number;
  raceName: string;
  offTime: string;
  distanceMiles: string;
  fieldSize: number;
  status: RaceStatus;
  settled: boolean;
  raceNumber: number;
  runners: Runner[];
}

export type RaceDayStatus = "loaded" | "pending" | "error";

export interface RaceDay {
  course: string;
  date: string;
  label?: string;
  status?: RaceDayStatus;
  races?: Array<{ id: string; off_time: string; name: string; status: string }>;
  last_refresh?: string | null;
  last_error?: string | null;
}

export interface Meeting {
  id: string;
  course: string;
  festival: string;
  days: string[];
  raceDays: RaceDay[];
  snapshotLocked: boolean;
}

export interface User { id: string; displayName: string; isAdmin: boolean; avatar: string; }
export interface Pick { userId: string; raceId: string; runnerId: string; }
export interface LeaderboardEntry {
  userId: string;
  displayName: string;
  totalPoints: number;
  dayPoints: number[];
  wins: number;
  places: number;
  dnfCount: number;
  position: number;
}

export interface AppData {
  meeting: Meeting | null;
  races: Race[];
  picks: Pick[];
  users: User[];
  leaderboard: LeaderboardEntry[];
  currentUserId: string;
  currentDayIndex: number;
  apiErrors: string[];
}
