export type Role = 'admin' | 'member';
export type Category = 'sweet' | 'savoury' | 'drink' | 'healthy-ish';
export type StockStatus = 'stocked' | 'running_low' | 'gone';

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
}

export interface Snack {
  id: number;
  name: string;
  category: Category;
  quantity: number;
  low_stock_threshold: number;
  status: StockStatus;
  votes: number;
  has_voted: boolean;
}

export interface SnackPage {
  items: Snack[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Summary {
  stocked: number;
  running_low: number;
  gone: number;
  total: number;
  snack_of_the_week: { id: number; name: string; category: Category; votes_this_week: number } | null;
}

export interface Activity {
  id: number;
  user_name: string;
  snack_name: string;
  action: 'consumed' | 'restocked';
  amount: number;
  created_at: string;
}

export interface ActivityPage {
  items: Activity[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SnackInput {
  name: string;
  category: Category;
  quantity?: number;
  low_stock_threshold: number;
}
