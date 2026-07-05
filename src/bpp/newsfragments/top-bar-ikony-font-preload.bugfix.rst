Ikony Foundation w górnym menu (``top_bar.html``) nie pokazywały się przez
chwilę jako "kwadraciki z kodem" (tofu) w Firefoksie, zanim font ikonowy się
doczytał. Font ``foundation-icons.woff`` jest teraz preloadowany w ``<head>``,
a ``@font-face`` ma wymuszone ``font-display: block`` — zamiast pudełek z kodem
widać pustkę, a po doczytaniu fontu ikona doskakuje.
