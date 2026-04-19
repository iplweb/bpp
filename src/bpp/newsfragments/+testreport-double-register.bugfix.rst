Usunięto ``RuntimeWarning: Model 'long_running.testreport' was
already registered`` w testach ``long_running``. Testowy model
``TestReport`` został przeniesiony z inline'owej definicji we
fixturze do ``test_bpp.models`` wraz z migracją, dzięki czemu
model jest rejestrowany w ``apps`` tylko raz, a nie przy każdym
wywołaniu fixture'a.
