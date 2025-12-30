"use client";

import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  pdf,
  Font,
  Image,
} from "@react-pdf/renderer";

// Register Inter font from Google Fonts
Font.register({
  family: "Inter",
  fonts: [
    {
      src: "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2",
      fontWeight: 400,
    },
    {
      src: "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuI6fAZ9hiJ-Ek-_EeA.woff2",
      fontWeight: 500,
    },
    {
      src: "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuGKYAZ9hiJ-Ek-_EeA.woff2",
      fontWeight: 600,
    },
    {
      src: "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuFuYAZ9hiJ-Ek-_EeA.woff2",
      fontWeight: 700,
    },
  ],
});

// Types
interface DecisionForReport {
  decision_number: number;
  title: string;
  status: string;
  created_at: string;
  tags: string[];
}

interface ReportData {
  organizationName: string;
  generatedBy: string;
  generatedAt: string;
  dateRange: {
    start: string;
    end: string;
  };
  filters: {
    statuses: string[] | string;
    tags: string[] | string;
  };
  stats: {
    total: number;
    approved: number;
    pending: number;
    draft: number;
  };
  decisions: DecisionForReport[];
  verificationHash: string;
}

// Modern theme colors matching the app
const colors = {
  primary: "#4f46e5",
  primaryLight: "#eef2ff",
  primaryDark: "#3730a3",
  success: "#10b981",
  successLight: "#d1fae5",
  successDark: "#065f46",
  warning: "#f59e0b",
  warningLight: "#fef3c7",
  warningDark: "#92400e",
  gray50: "#f9fafb",
  gray100: "#f3f4f6",
  gray200: "#e5e7eb",
  gray400: "#9ca3af",
  gray500: "#6b7280",
  gray600: "#4b5563",
  gray700: "#374151",
  gray900: "#111827",
  white: "#ffffff",
};

// Styles
const styles = StyleSheet.create({
  page: {
    padding: 0,
    fontFamily: "Inter",
    fontSize: 10,
    color: colors.gray700,
    backgroundColor: colors.white,
  },
  headerBand: {
    backgroundColor: colors.primary,
    height: 6,
  },
  header: {
    padding: 32,
    paddingTop: 24,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
  },
  headerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
  },
  logoSection: {
    flexDirection: "row",
    alignItems: "center",
  },
  logoImage: {
    width: 40,
    height: 40,
    marginRight: 12,
  },
  brandName: {
    fontSize: 18,
    fontWeight: 700,
    color: colors.gray900,
  },
  brandTagline: {
    fontSize: 10,
    color: colors.gray500,
    marginTop: 2,
    fontWeight: 400,
  },
  reportType: {
    backgroundColor: colors.gray900,
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 20,
  },
  reportTypeText: {
    fontSize: 9,
    color: colors.white,
    fontWeight: 600,
    letterSpacing: 0.5,
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: colors.gray900,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: colors.gray500,
    fontWeight: 400,
  },
  complianceBadges: {
    flexDirection: "row",
    marginTop: 16,
  },
  complianceBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.successLight,
    paddingVertical: 5,
    paddingHorizontal: 12,
    borderRadius: 14,
    marginRight: 8,
  },
  complianceBadgeText: {
    fontSize: 9,
    color: colors.successDark,
    fontWeight: 600,
  },
  content: {
    padding: 32,
    paddingBottom: 60,
  },
  infoCardsRow: {
    flexDirection: "row",
    marginBottom: 28,
    backgroundColor: colors.gray50,
    borderRadius: 16,
    padding: 20,
  },
  infoCard: {
    flex: 1,
    paddingRight: 20,
    borderRightWidth: 1,
    borderRightColor: colors.gray200,
  },
  infoCardLast: {
    borderRightWidth: 0,
    paddingRight: 0,
    paddingLeft: 20,
  },
  infoCardMiddle: {
    paddingLeft: 20,
  },
  infoCardLabel: {
    fontSize: 10,
    color: colors.gray500,
    textTransform: "uppercase",
    marginBottom: 6,
    fontWeight: 500,
    letterSpacing: 0.5,
  },
  infoCardValue: {
    fontSize: 13,
    color: colors.gray900,
    fontWeight: 600,
  },
  statsSection: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  sectionIcon: {
    width: 24,
    height: 24,
    backgroundColor: colors.primaryLight,
    borderRadius: 6,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 10,
  },
  sectionIconText: {
    fontSize: 12,
    color: colors.primary,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "bold",
    color: colors.gray900,
  },
  statsGrid: {
    flexDirection: "row",
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.gray50,
    borderRadius: 12,
    padding: 16,
    marginRight: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.gray100,
  },
  statCardLast: {
    marginRight: 0,
  },
  statNumber: {
    fontSize: 28,
    fontWeight: "bold",
    color: colors.primary,
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 9,
    color: colors.gray500,
    textTransform: "uppercase",
  },
  tableSection: {
    marginBottom: 24,
  },
  table: {
    borderWidth: 1,
    borderColor: colors.gray200,
    borderRadius: 12,
    overflow: "hidden",
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: colors.gray900,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  tableHeaderCell: {
    color: colors.white,
    fontWeight: 600,
    fontSize: 9,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  tableRow: {
    flexDirection: "row",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
    alignItems: "flex-start",
  },
  tableRowAlt: {
    backgroundColor: colors.gray50,
  },
  tableCell: {
    fontSize: 9,
    color: colors.gray700,
    fontWeight: 400,
  },
  colNumber: {
    width: 70,
  },
  colTitle: {
    flex: 1,
    paddingRight: 16,
  },
  colStatus: {
    width: 100,
  },
  colDate: {
    width: 85,
    textAlign: "right",
  },
  statusBadge: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
    fontSize: 7,
    textAlign: "center",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  statusApproved: {
    backgroundColor: colors.successLight,
    color: colors.successDark,
  },
  statusPending: {
    backgroundColor: colors.warningLight,
    color: colors.warningDark,
  },
  statusDraft: {
    backgroundColor: colors.gray100,
    color: colors.gray600,
  },
  statusDeprecated: {
    backgroundColor: "#fee2e2",
    color: "#991b1b",
  },
  moreRows: {
    padding: 12,
    alignItems: "center",
    backgroundColor: colors.gray50,
  },
  moreRowsText: {
    fontSize: 9,
    color: colors.gray500,
  },
  hashSection: {
    backgroundColor: colors.gray50,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.gray200,
  },
  hashHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  hashIcon: {
    width: 20,
    height: 20,
    backgroundColor: colors.gray900,
    borderRadius: 4,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  hashIconText: {
    fontSize: 10,
    color: colors.white,
    fontWeight: 600,
  },
  hashTitle: {
    fontSize: 11,
    fontWeight: 600,
    color: colors.gray900,
  },
  hashValue: {
    fontSize: 8,
    color: colors.gray600,
    fontFamily: "Courier",
    backgroundColor: colors.white,
    padding: 12,
    borderRadius: 8,
    marginTop: 4,
    borderWidth: 1,
    borderColor: colors.gray200,
  },
  hashNote: {
    fontSize: 9,
    color: colors.gray500,
    marginTop: 8,
    fontWeight: 400,
  },
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.gray200,
    padding: 20,
    paddingHorizontal: 32,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  footerLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  footerLogoImage: {
    width: 18,
    height: 18,
    marginRight: 8,
  },
  footerBrand: {
    fontSize: 9,
    color: colors.gray500,
    fontWeight: 400,
  },
  footerRight: {
    fontSize: 9,
    color: colors.gray400,
    fontWeight: 500,
  },
});

// Get status style
function getStatusStyle(status: string) {
  switch (status) {
    case "approved":
      return styles.statusApproved;
    case "pending_review":
      return styles.statusPending;
    case "draft":
      return styles.statusDraft;
    case "deprecated":
    case "superseded":
      return styles.statusDeprecated;
    default:
      return styles.statusDraft;
  }
}

// Format date
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateString;
  }
}

// Logo URL - using the public icon
const LOGO_URL = "https://app.imputable.io/icon.png";

// PDF Document Component
function AuditReportDocument({ data }: { data: ReportData }) {
  return (
    <Document>
      <Page size="A4" style={styles.page}>
        {/* Header Band */}
        <View style={styles.headerBand} />

        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerTop}>
            <View style={styles.logoSection}>
              <Image src={LOGO_URL} style={styles.logoImage} />
              <View>
                <Text style={styles.brandName}>Imputable</Text>
                <Text style={styles.brandTagline}>Decision Ledger</Text>
              </View>
            </View>
            <View style={styles.reportType}>
              <Text style={styles.reportTypeText}>AUDIT REPORT</Text>
            </View>
          </View>

          <Text style={styles.title}>Compliance Report</Text>
          <Text style={styles.subtitle}>{data.organizationName}</Text>

          <View style={styles.complianceBadges}>
            <View style={styles.complianceBadge}>
              <Text style={styles.complianceBadgeText}>SOC2 Ready</Text>
            </View>
            <View style={styles.complianceBadge}>
              <Text style={styles.complianceBadgeText}>ISO 27001</Text>
            </View>
            <View style={styles.complianceBadge}>
              <Text style={styles.complianceBadgeText}>HIPAA</Text>
            </View>
          </View>
        </View>

        {/* Content */}
        <View style={styles.content}>
          {/* Info Cards - Redesigned as a clean bar */}
          <View style={styles.infoCardsRow}>
            <View style={styles.infoCard}>
              <Text style={styles.infoCardLabel}>Generated By</Text>
              <Text style={styles.infoCardValue}>{data.generatedBy}</Text>
            </View>
            <View style={[styles.infoCard, styles.infoCardMiddle]}>
              <Text style={styles.infoCardLabel}>Date Range</Text>
              <Text style={styles.infoCardValue}>
                {formatDate(data.dateRange.start)} -{" "}
                {formatDate(data.dateRange.end)}
              </Text>
            </View>
            <View style={[styles.infoCard, styles.infoCardLast]}>
              <Text style={styles.infoCardLabel}>Generated At</Text>
              <Text style={styles.infoCardValue}>
                {formatDate(data.generatedAt)}
              </Text>
            </View>
          </View>

          {/* Stats Section */}
          <View style={styles.statsSection}>
            <View style={styles.sectionHeader}>
              <View style={styles.sectionIcon}>
                <Text style={styles.sectionIconText}>#</Text>
              </View>
              <Text style={styles.sectionTitle}>Decision Statistics</Text>
            </View>
            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Text style={styles.statNumber}>{data.stats.total}</Text>
                <Text style={styles.statLabel}>Total</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statNumber, { color: colors.success }]}>
                  {data.stats.approved}
                </Text>
                <Text style={styles.statLabel}>Approved</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statNumber, { color: colors.warning }]}>
                  {data.stats.pending}
                </Text>
                <Text style={styles.statLabel}>Pending</Text>
              </View>
              <View style={[styles.statCard, styles.statCardLast]}>
                <Text style={[styles.statNumber, { color: colors.gray500 }]}>
                  {data.stats.draft}
                </Text>
                <Text style={styles.statLabel}>Draft</Text>
              </View>
            </View>
          </View>

          {/* Decisions Table */}
          <View style={styles.tableSection}>
            <View style={styles.sectionHeader}>
              <View style={styles.sectionIcon}>
                <Text style={styles.sectionIconText}>D</Text>
              </View>
              <Text style={styles.sectionTitle}>
                Decisions ({data.decisions.length})
              </Text>
            </View>
            <View style={styles.table}>
              {/* Table Header */}
              <View style={styles.tableHeader}>
                <Text style={[styles.tableHeaderCell, styles.colNumber]}>
                  Number
                </Text>
                <Text style={[styles.tableHeaderCell, styles.colTitle]}>
                  Title
                </Text>
                <Text style={[styles.tableHeaderCell, styles.colStatus]}>
                  Status
                </Text>
                <Text style={[styles.tableHeaderCell, styles.colDate]}>
                  Created
                </Text>
              </View>

              {/* Table Rows - Show full titles */}
              {data.decisions.slice(0, 20).map((decision, index) => (
                <View
                  key={decision.decision_number}
                  style={[
                    styles.tableRow,
                    index % 2 === 1 ? styles.tableRowAlt : {},
                  ]}
                  wrap={false}
                >
                  <Text style={[styles.tableCell, styles.colNumber]}>
                    DEC-{decision.decision_number}
                  </Text>
                  <Text style={[styles.tableCell, styles.colTitle]}>
                    {decision.title}
                  </Text>
                  <View style={styles.colStatus}>
                    <Text
                      style={[
                        styles.statusBadge,
                        getStatusStyle(decision.status),
                      ]}
                    >
                      {decision.status.replace(/_/g, " ")}
                    </Text>
                  </View>
                  <Text style={[styles.tableCell, styles.colDate]}>
                    {formatDate(decision.created_at)}
                  </Text>
                </View>
              ))}

              {data.decisions.length > 20 && (
                <View style={styles.moreRows}>
                  <Text style={styles.moreRowsText}>
                    + {data.decisions.length - 20} more decisions in full export
                  </Text>
                </View>
              )}
            </View>
          </View>

          {/* Verification Hash */}
          <View style={styles.hashSection}>
            <View style={styles.hashHeader}>
              <View style={styles.hashIcon}>
                <Text style={styles.hashIconText}>*</Text>
              </View>
              <Text style={styles.hashTitle}>
                Cryptographic Verification (SHA-256)
              </Text>
            </View>
            <Text style={styles.hashValue}>{data.verificationHash}</Text>
            <Text style={styles.hashNote}>
              This hash verifies the authenticity and integrity of this report.
            </Text>
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer} fixed>
          <View style={styles.footerLeft}>
            <Image src={LOGO_URL} style={styles.footerLogoImage} />
            <Text style={styles.footerBrand}>
              Generated by Imputable - Decision Ledger
            </Text>
          </View>
          <Text
            style={styles.footerRight}
            render={({ pageNumber, totalPages }) =>
              `Page ${pageNumber} of ${totalPages}`
            }
          />
        </View>
      </Page>
    </Document>
  );
}

// Export function to generate PDF blob
export async function generateAuditPDF(data: ReportData): Promise<Blob> {
  const doc = <AuditReportDocument data={data} />;
  const blob = await pdf(doc).toBlob();
  return blob;
}

export type { ReportData, DecisionForReport };
