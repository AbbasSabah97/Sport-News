import Foundation
import SwiftUI
import Combine

enum Theme {
    static let bg = Color(red: 0.025, green: 0.056, blue: 0.103)
    static let surface = Color(red: 0.064, green: 0.113, blue: 0.178)
    static let raised = Color(red: 0.105, green: 0.165, blue: 0.258)
    static let blue = Color(red: 0.13, green: 0.45, blue: 0.98)
    static let cyan = Color(red: 0.34, green: 0.80, blue: 1.0)
    static let muted = Color(red: 0.66, green: 0.74, blue: 0.83)
}
struct FeedSnapshot: Decodable {
    let schemaVersion: Int
    let generatedAt: String
    let timezone: String
    let localDate: String
    let newsStatus: String
    let news: [Article]
    let digest: [DigestStory]
    let digestNote: String
    let sourceWarnings: [String]
    let sportsStatus: String
    let sportsError: String?
    let competitions: [Competition]
    let matches: [FootballMatch]
    var preview: Bool { newsStatus == "demo" }
}
struct Article: Decodable, Identifiable {
    let id: String
    let title: String
    let summary: String
    let url: String
    let source: String
    let language: String
    let publishedAt: String
    let sourceCount: Int
    let relatedSources: [String]
    let category: String
    let rank: Double
    var destination: URL? {
        guard let u=URL(string:url), u.scheme=="https" else { return nil }
        return u
    }
}
struct DigestStory: Decodable, Identifiable {
    let id: String
    let headline: String
    let source: String
    let sourceCount: Int
    let url: String
    let category: String
    var destination: URL? {
        guard let u=URL(string:url),u.scheme=="https" else { return nil }
        return u
    }
}
struct Competition: Decodable, Identifiable {
    let id: String
    let name: String
}
struct FootballMatch: Decodable, Identifiable {
    let id: String
    let competitionId: String
    let league: String
    let home: String
    let away: String
    let homeGoals: Int?
    let awayGoals: Int?
    let kickoff: String
    let status: String
}
enum DateUtil {
    static let zone = TimeZone(identifier:"Asia/Baghdad")!
    static func parse(_ string:String) -> Date? {
        let f=ISO8601DateFormatter()
        f.formatOptions=[.withInternetDateTime,.withFractionalSeconds]
        if let date=f.date(from:string) { return date }
        f.formatOptions=[.withInternetDateTime]
        return f.date(from:string)
    }
    static func format(_ date:String, clock:Bool=true) -> String {
        guard let parsed=parse(date) else {return "—"}
        let df=DateFormatter()
        df.locale=Locale(identifier:"ar_IQ")
        df.timeZone=zone
        df.dateFormat=clock ? "h:mm a" : "d MMM yyyy"
        return df.string(from:parsed)
    }
    static func today() -> String {
        let df=DateFormatter()
        df.timeZone=zone
        df.dateFormat="yyyy-MM-dd"
        return df.string(from:Date())
    }
}
@MainActor
final class FeedStore: ObservableObject {
    @Published var feed: FeedSnapshot?
    @Published var loading=false
    @Published var error: String?
    @Published var favorites: Set<String> = []
    private var lastLoad: Date?
    private static var legacyCacheURL: URL {
        FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0].appendingPathComponent("sport-news-feed.json")
    }
    static let decoder: JSONDecoder = {
        let d=JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()
    init() {
        URLCache.shared.removeAllCachedResponses()
        URLCache.shared.diskCapacity=0
        URLCache.shared.memoryCapacity=0
        try? FileManager.default.removeItem(at:Self.legacyCacheURL)
        favorites=Set((UserDefaults.standard.stringArray(forKey:"favorites") ?? []).prefix(200))
        if let url=Bundle.main.url(forResource:"preview-feed",withExtension:"json"),
           let bytes=try? Data(contentsOf:url),
           let snap=try? Self.decoder.decode(FeedSnapshot.self,from:bytes) {
            feed=snap
        }
    }
    func toggleFavorite(_ id:String) {
        if favorites.contains(id) {favorites.remove(id)}
        else if favorites.count < 200 {favorites.insert(id)}
        UserDefaults.standard.set(Array(favorites).sorted(),forKey:"favorites")
    }
    var stale: Bool {
        guard let feed else {return true}
        if feed.preview {return false}
        guard let d=DateUtil.parse(feed.generatedAt) else {return true}
        return Date().timeIntervalSince(d)>7200 || feed.localDate != DateUtil.today() || feed.newsStatus=="stale" || feed.sportsStatus=="stale"
    }
    func refresh(feedURL:String,force:Bool=false) async {
        if loading {return}
        if !force,let last=lastLoad,Date().timeIntervalSince(last)<240 {return}
        let input=feedURL.trimmingCharacters(in:.whitespacesAndNewlines)
        let endpoint=input.isEmpty ? FeedEndpoint.generatedURL : input
        guard let u=URL(string:endpoint),u.scheme=="https",u.host != nil else {
            error="رابط البيانات غير مضبوط؛ يعرض التطبيق حالياً البيانات التجريبية."
            return
        }
        loading=true
        lastLoad=Date()
        defer {loading=false}
        do {
            let configuration=URLSessionConfiguration.ephemeral
            configuration.urlCache=nil
            configuration.httpCookieStorage=nil
            configuration.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
            let session=URLSession(configuration:configuration)
            defer {session.invalidateAndCancel()}
            var req=URLRequest(url:u)
            req.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
            req.timeoutInterval=20
            req.setValue("no-store",forHTTPHeaderField:"Cache-Control")
            let (data,response)=try await session.data(for:req)
            guard data.count <= 350_000 else {throw URLError(.dataLengthExceedsMaximum)}
            guard (response as? HTTPURLResponse)?.statusCode==200 else {
                throw URLError(.badServerResponse)
            }
            let snap=try Self.decoder.decode(FeedSnapshot.self,from:data)
            guard snap.schemaVersion == 1 else {throw URLError(.cannotParseResponse)}
            feed=snap
            error=nil
        } catch {
            self.error="تعذر تحديث البيانات: "+error.localizedDescription
        }
    }
}
