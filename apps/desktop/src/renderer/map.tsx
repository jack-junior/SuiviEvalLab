// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// A small OpenStreetMap map (Leaflet): shows a position and lets the user pick one
// by clicking. Tiles need a connection; without one the map stays grey and the
// position can still be typed.

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

export interface Position {
  lat: number;
  lon: number;
}

export function MapPicker({
  position,
  onPick,
  label,
}: {
  position: Position | null;
  onPick: (p: Position) => void;
  label: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const pick = useRef(onPick);
  useEffect(() => {
    pick.current = onPick;
  }, [onPick]);

  useEffect(() => {
    if (!box.current) return;
    const m = L.map(box.current, { zoomControl: true, attributionControl: true }).setView([8, 1], 3);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) =>
      pick.current({ lat: Number(e.latlng.lat.toFixed(6)), lon: Number(e.latlng.lng.toFixed(6)) }),
    );
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      marker.current = null;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!position) {
      marker.current?.remove();
      marker.current = null;
      return;
    }
    const at: L.LatLngExpression = [position.lat, position.lon];
    if (marker.current) marker.current.setLatLng(at);
    else marker.current = L.circleMarker(at, { radius: 8, color: "#1d4f91", weight: 3, fillOpacity: 0.4 }).addTo(m);
    m.setView(at, Math.max(m.getZoom(), 11));
  }, [position]);

  return <div ref={box} className="map-picker" role="application" aria-label={label} data-testid="map" />;
}
