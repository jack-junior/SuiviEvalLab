// Static assets imported by the interface (Vite returns their URL).
declare module "*.svg" {
  const url: string;
  export default url;
}
