import type { Metadata } from "next";
import "./style.css";

export const metadata: Metadata = {
  title: "AYE | Autonomous YouTube Engine",
  description: "Manage channel configuration and the content pipeline.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
