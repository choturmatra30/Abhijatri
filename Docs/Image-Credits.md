# Image credits

Every photograph the public app shows, with its licence. Platform Foundation 17 allows only team-owned, explicitly licensed, open-licence (with attribution) or public-domain images; this file is the record for the open-licence ones. Add a row here in the same change that adds an image, and never add an image without one.

**How the images are used.** Each photo was downloaded from Wikimedia Commons on 4 November 2026, resized to at most 1024 px wide and re-encoded as WebP (which also removes EXIF and GPS metadata), and is self-hosted under `frontend/public/images/destinations/`, so the site never hotlinks. The app shows the author (linked to the source page), the licence (linked) and "resized" on the photo wherever it appears (`components/common/ImageCredit.tsx`). The data lives in `frontend/src/data/destinationImages.ts`.

**Share-alike.** These licences are CC BY-SA. The resized copies are shared under the same licence as their originals.

| Destination | File (self-hosted) | Shows | Author | Licence | Source |
|---|---|---|---|---|---|
| Cox's Bazar | `coxs-bazar.webp` (1024 × 682, 22 KB) | People on the beach at sunset | Tanweer Morshed | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) | [Cox's Bazar sea beach 01.jpg](https://commons.wikimedia.org/wiki/File:Cox%27s_Bazar_sea_beach_01.jpg) |
| Sajek Valley | `sajek-valley.webp` (1024 × 683, 89 KB) | Clouds between the hills | Sahriar ahmed tasvir | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | [Clouds at Sajek Valley 20171220.jpg](https://commons.wikimedia.org/wiki/File:Clouds_at_Sajek_Valley_20171220.jpg) |
| Sylhet | `sylhet.webp` (1024 × 682, 179 KB) | A boat in Ratargul Swamp Forest | Sumon Mallick | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | [Ratargul Swamp Forest, Sylhet..jpg](https://commons.wikimedia.org/wiki/File:Ratargul_Swamp_Forest,_Sylhet..jpg) |
| Sundarbans | `sundarbans.webp` (1024 × 682, 161 KB) | Mangrove forest along a river at Karamjal (Bangladesh side) | Shahid BDWiki | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | [Karamjal Point, SUNDARBAN.jpg](https://commons.wikimedia.org/wiki/File:Karamjal_Point,_SUNDARBAN.jpg) |
| Bandarban | `bandarban.webp` (1024 × 576, 58 KB) | Hill ranges seen from Nilgiri | Tanvir Rahat | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | [Nilgiri, Bandarban, Bangladesh.jpg](https://commons.wikimedia.org/wiki/File:Nilgiri,_Bandarban,_Bangladesh.jpg) |

Licence and author were read from each file's Commons metadata (`extmetadata`), not assumed. Candidates rejected: several Sundarbans photos from West Bengal, India (wrong country for these guides), and a Kotka photo that showed open grassland rather than the mangrove.
