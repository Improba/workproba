export default {
  apiUrl(): string {
    let apiUrl = `${process.env.API_URL}`;
    if (!apiUrl) {
      const w = window as any;
      const s = self as any;
      apiUrl = !s.__IS_WORKER ? w.__API_URL : s.__API_URL;
    }

    return apiUrl;
  },
};
