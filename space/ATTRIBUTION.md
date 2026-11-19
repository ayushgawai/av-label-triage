# Public image provenance

`manila-crossing.jpg`: “Pedestrians crossing the street in Sampaloc, Manila (2024)” by [PhiliptheNumber1](https://commons.wikimedia.org/wiki/User:PhiliptheNumber1), [source on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Pedestrians_crossing_the_street_in_Sampaloc,_Manila_(2024).jpg), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The downloaded original is unchanged. SHA-256: `1a18237735278f218b7bdb952ecaab7e40c9d215b77199c45f59ddc229983377`. Attribution and license link must accompany public display; mark any subsequent modifications.

This is a separate public photograph, not KITTI or a historical missed-label case. It has visible pedestrians but **no documented human box pass or independent review**. Do not present its annotations, seeded omissions, audit estimates, or model results as real reviewed findings until those artifacts exist and are identified accurately.

## COCO 2017 validation photographs and boxes

`coco/annotations.json` contains the COCO 2017 validation annotations for five images, retaining all original categories and boxes while removing segmentation polygons. The labels are original human-produced COCO annotations, not a new exhaustive reviewer pass; any deliberately removed boxes must be identified as seeded. The [COCO Consortium licenses annotations under CC BY 4.0](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/termsofuse.htm); cite Lin et al., “Microsoft COCO: Common Objects in Context” (2014), https://arxiv.org/abs/1405.0312. Images have independent licenses: the source Flickr pages and COCO metadata each identify the images below as [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/). These files are the distributed COCO derivatives, not the original-resolution photos; image resizing is a modification. Include photographer, source and license link when displaying each image.

| COCO image | Attribution and source | SHA-256 of downloaded COCO file |
|---|---|---|
| 142472 | [Elliott Brown, Golders Green Road](https://www.flickr.com/photos/ell-r-brown/7871818696/) | `db7173813c230d969afa81c1012904f95a680a4b6b756eb07e17e6727c88c0dd` |
| 184324 | [Serge Melki, Carrefour - St. André des Arts](https://www.flickr.com/photos/sergemelki/3364389746/) | `5bfec85c40197744fc7fa8262a0a0e14ad1a6fc0e11cee4b7b0c5df97a146107` |
| 210273 | [Tauno Tõhk, Wuhan](https://www.flickr.com/photos/toehk/5336041838/) | `3ec23de63592c1eef86740fd46fed2cb66170fca02b695d37e6ae379dcee4355` |
| 301376 | [Chad Kainz, North Avenue](https://www.flickr.com/photos/smaedli/2718408461/) | `57ead4a94a6df986a161c014c0719b6c37b52ea2aa2246c297ec44db06eb7a2e` |
| 309391 | [Ian Sane, Life under a Canopy](https://www.flickr.com/photos/31246066@N04/5329327710/) | `8ed212a0ffcf1b3d5f1fb307839030fb41aed1ff7488845a3bed02e386474082` |

The subset has 145 original box annotations, including 51 person boxes. COCO annotations do not establish exhaustive box completeness or qualify as an independent human pilot.
