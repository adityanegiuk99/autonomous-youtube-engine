import type { Metadata } from "next";
import "./style.css";
import { ApiSession } from "./components/api-session";

export const metadata: Metadata = {
  title: "AYE | Autonomous YouTube Engine",
  description: "Manage channel configuration and the content pipeline.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><ApiSession>{children}</ApiSession></body></html>;
}
