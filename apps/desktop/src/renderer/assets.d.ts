// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Static assets imported by the interface (Vite returns their URL).
declare module "*.svg" {
  const url: string;
  export default url;
}
