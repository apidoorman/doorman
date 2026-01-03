REST_TARGETS = [
    ("https://httpbin.org", "/get"),
    ("https://api.github.com", "/"),
    ("https://jsonplaceholder.typicode.com", "/posts/1"),
    ("https://jsonplaceholder.typicode.com", "/todos/1"),
    ("https://catfact.ninja", "/fact"),
]

# SOAP targets: (server, uri, envelope_kind, soap_action)
SOAP_TARGETS = [
    ("http://www.dneonline.com", "/calculator.asmx", "calc", "http://tempuri.org/Add"),
    (
        "http://webservices.oorsprong.org",
        "/websamples.countryinfo/CountryInfoService.wso",
        "country",
        "http://www.oorsprong.org/websamples.countryinfo/CountryInfoService.wso/CapitalCity",
    ),
    (
        "https://www.w3schools.com",
        "/xml/tempconvert.asmx",
        "temp",
        "https://www.w3schools.com/xml/CelsiusToFahrenheit",
    ),
    (
        "https://www.dataaccess.com",
        "/webservicesserver/NumberConversion.wso",
        "num",
        "http://www.dataaccess.com/webservicesserver/NumberConversion.wso/NumberToWords",
    ),
]

# GraphQL targets: server must accept /graphql (gateway appends /graphql)
GRAPHQL_TARGETS = [
    ("https://countries.trevorblades.com", "{ countries { code name } }"),
    ("https://countries.trevorblades.com", "{ country(code: \"US\") { name capital } }"),
    ("https://countries.trevorblades.com", "{ continents { code name } }"),
]

# gRPC targets: (server, method)
GRPC_TARGETS = [
    ("grpc://grpcb.in:9000", "GRPCBin.Empty"),
    ("grpcs://grpcb.in:9001", "GRPCBin.Empty"),
    ("grpc://grpcb.in:9000", "GRPCBin.Empty"),
]
