/**
 * RowLevelIssuesSection - Displays detailed row-by-row issues
 * Consistent with other result section components
 */
import React, { useState } from "react";
import styled from "styled-components";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, ChevronDown, ChevronUp, Filter } from "lucide-react";
import {
  Section,
  SectionTitle,
  SectionDescription,
  ChartsGrid,
} from "./SharedStyledComponents";
import { sectionVariants } from "./animationVariants";
import { TooltipIcon } from "./Tooltip";
import RechartsPieChart from "../charts/RechartsPieChart";

const FilterContainer = styled.div`
  display: flex;
  gap: ${(props) => props.theme.spacing.sm};
  flex-wrap: wrap;
  margin-bottom: ${(props) => props.theme.spacing.lg};
  padding: ${(props) => props.theme.spacing.md};
  background: ${(props) => props.theme.colors.background};
  border-radius: ${(props) => props.theme.borderRadius.lg};
  align-items: center;
`;

const FilterLabel = styled.span`
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
  font-weight: ${(props) => props.theme.typography.fontWeights.semibold};
  color: ${(props) => props.theme.colors.text.primary};
  display: flex;
  align-items: center;
  gap: ${(props) => props.theme.spacing.xs};
`;

const FilterBtn = styled.button`
  padding: ${(props) => props.theme.spacing.xs}
    ${(props) => props.theme.spacing.md};
  border-radius: ${(props) => props.theme.borderRadius.full};
  border: 1px solid
    ${(props) =>
      props.$active ? props.theme.colors.primary : props.theme.colors.border};
  background: ${(props) =>
    props.$active ? props.theme.colors.primary : props.theme.colors.surface};
  color: ${(props) =>
    props.$active ? "white" : props.theme.colors.text.secondary};
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
  font-weight: ${(props) => props.theme.typography.fontWeights.medium};
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: ${(props) => props.theme.spacing.xs};

  &:hover {
    background: ${(props) =>
      props.$active
        ? props.theme.colors.primary
        : props.theme.colors.background};
    transform: translateY(-1px);
  }
`;

const StatsContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: ${(props) => props.theme.spacing.lg};
  margin-bottom: ${(props) => props.theme.spacing.xl};
`;

const StatBox = styled(motion.div)`
  background: ${(props) => props.theme.colors.surface};
  border-radius: ${(props) => props.theme.borderRadius.lg};
  padding: ${(props) => props.theme.spacing.lg};
  box-shadow: ${(props) => props.theme.shadows.sm};
  border-left: 4px solid
    ${(props) => props.$color || props.theme.colors.primary};
  transition: all 0.2s ease;

  &:hover {
    box-shadow: ${(props) => props.theme.shadows.md};
    transform: translateY(-2px);
  }
`;

const StatNumber = styled.div`
  font-size: ${(props) => props.theme.typography.fontSizes.xxl};
  font-weight: ${(props) => props.theme.typography.fontWeights.bold};
  color: ${(props) => props.$color || props.theme.colors.text.primary};
  margin-bottom: ${(props) => props.theme.spacing.xs};
`;

const StatName = styled.div`
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
  color: ${(props) => props.theme.colors.text.secondary};
  font-weight: ${(props) => props.theme.typography.fontWeights.medium};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: ${(props) => props.theme.spacing.xs};
`;

const TableContainer = styled.div`
  overflow-x: auto;
  border-radius: ${(props) => props.theme.borderRadius.lg};
  border: 1px solid ${(props) => props.theme.colors.border};
  margin-bottom: ${(props) => props.theme.spacing.xl};
  padding: 0;

  /* Allow tooltips to overflow */
  overflow-y: visible;

  table {
    position: relative;
    z-index: 1;
  }
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
`;

const Thead = styled.thead`
  background: ${(props) => props.theme.colors.background};
  border-bottom: 2px solid ${(props) => props.theme.colors.border};
`;

const Th = styled.th`
  padding: ${(props) => props.theme.spacing.md};
  text-align: left;
  font-weight: ${(props) => props.theme.typography.fontWeights.semibold};
  color: ${(props) => props.theme.colors.text.primary};
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
  white-space: nowrap;
`;

const Tbody = styled.tbody``;

const Tr = styled(motion.tr)`
  border-bottom: 1px solid ${(props) => props.theme.colors.border};
  transition: background 0.2s ease;

  &:hover {
    background: ${(props) => props.theme.colors.background};
  }

  &:last-child {
    border-bottom: none;
  }
`;

const Td = styled.td`
  padding: ${(props) => props.theme.spacing.md};
  color: ${(props) => props.theme.colors.text.secondary};
  vertical-align: middle;
`;

const SeverityBadge = styled.span`
  padding: 4px 12px;
  border-radius: ${(props) => props.theme.borderRadius.full};
  font-size: ${(props) => props.theme.typography.fontSizes.xs};
  font-weight: ${(props) => props.theme.typography.fontWeights.semibold};
  text-transform: uppercase;
  background: ${(props) => {
    switch (props.$severity) {
      case "critical":
        return "#ef444410";
      case "warning":
        return "#f59e0b10";
      default:
        return "#3b82f610";
    }
  }};
  color: ${(props) => {
    switch (props.$severity) {
      case "critical":
        return "#ef4444";
      case "warning":
        return "#f59e0b";
      default:
        return "#3b82f6";
    }
  }};
  border: 1px solid
    ${(props) => {
      switch (props.$severity) {
        case "critical":
          return "#ef444440";
        case "warning":
          return "#f59e0b40";
        default:
          return "#3b82f640";
      }
    }};
`;

const IssueTypeBadge = styled.span`
  padding: 4px 10px;
  border-radius: ${(props) => props.theme.borderRadius.md};
  font-size: ${(props) => props.theme.typography.fontSizes.xs};
  font-weight: ${(props) => props.theme.typography.fontWeights.medium};
  background: ${(props) => props.theme.colors.background};
  color: ${(props) => props.theme.colors.text.secondary};
  font-family: monospace;
`;

const ExpandBtn = styled.button`
  background: none;
  border: none;
  color: ${(props) => props.theme.colors.primary};
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
  padding: ${(props) => props.theme.spacing.xs};
  border-radius: ${(props) => props.theme.borderRadius.md};
  transition: all 0.2s ease;
  font-weight: ${(props) => props.theme.typography.fontWeights.medium};

  &:hover {
    background: ${(props) => props.theme.colors.primary}10;
  }
`;

const DetailsRow = styled(motion.tr)`
  background: ${(props) => props.theme.colors.background};
`;

const DetailsCell = styled.td`
  padding: ${(props) => props.theme.spacing.lg};
  border-bottom: 1px solid ${(props) => props.theme.colors.border};
`;

const DetailsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: ${(props) => props.theme.spacing.md};
`;

const DetailItem = styled.div`
  padding: ${(props) => props.theme.spacing.md};
  background: ${(props) => props.theme.colors.surface};
  border-radius: ${(props) => props.theme.borderRadius.md};
  border-left: 3px solid ${(props) => props.theme.colors.primary}40;
`;

const DetailLabel = styled.div`
  font-size: ${(props) => props.theme.typography.fontSizes.xs};
  color: ${(props) => props.theme.colors.text.secondary};
  margin-bottom: ${(props) => props.theme.spacing.xs};
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: ${(props) => props.theme.typography.fontWeights.semibold};
  display: flex;
  align-items: center;
  gap: ${(props) => props.theme.spacing.xs};
`;

const DetailValue = styled.div`
  font-size: ${(props) => props.theme.typography.fontSizes.sm};
  color: ${(props) => props.theme.colors.text.primary};
  font-weight: ${(props) => props.theme.typography.fontWeights.medium};
  word-break: break-word;
  font-family: monospace;
`;

const EmptyState = styled(motion.div)`
  text-align: center;
  padding: ${(props) => props.theme.spacing.xxl};
  color: ${(props) => props.theme.colors.text.secondary};
  background: ${(props) => props.theme.colors.background};
  border-radius: ${(props) => props.theme.borderRadius.lg};
`;

const EmptyIcon = styled.div`
  font-size: 3rem;
  margin-bottom: ${(props) => props.theme.spacing.md};
  opacity: 0.5;
`;

const ChartsSection = styled.div`
  margin-top: ${(props) => props.theme.spacing.xl};
  margin-bottom: ${(props) => props.theme.spacing.xl};
`;

const RowLevelIssuesSection = ({ unifiedData }) => {
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [expandedRows, setExpandedRows] = useState(new Set());

  if (
    !unifiedData ||
    !unifiedData.rowLevelIssues ||
    unifiedData.rowLevelIssues.length === 0
  ) {
    return null;
  }

  const { rowLevelIssues, issueSummary } = unifiedData;

  // Filter issues by severity
  const filteredIssues =
    selectedSeverity === "all"
      ? rowLevelIssues
      : rowLevelIssues.filter((issue) => issue.severity === selectedSeverity);

  // Count severities
  const severityCounts = {
    critical: rowLevelIssues.filter((i) => i.severity === "critical").length,
    warning: rowLevelIssues.filter((i) => i.severity === "warning").length,
    info: rowLevelIssues.filter((i) => i.severity === "info").length,
  };

  // Prepare data for charts
  const issuesByType = issueSummary?.by_type
    ? Object.entries(issueSummary.by_type).map(([type, count]) => ({
        name: type.replace(/_/g, " "),
        value: count,
      }))
    : [];

  const issuesBySeverity = [
    { name: "Critical", value: severityCounts.critical, color: "#ef4444" },
    { name: "Warning", value: severityCounts.warning, color: "#f59e0b" },
    { name: "Info", value: severityCounts.info, color: "#3b82f6" },
  ].filter((item) => item.value > 0);

  const toggleRow = (index) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <Section
      variants={sectionVariants}
      initial="hidden"
      animate="visible"
      transition={{ delay: 0.4 }}
    >
      <SectionTitle>
        <AlertTriangle size={28} />
        Row-Level Issues
        <TooltipIcon text="Specific data quality issues detected at individual row level, categorized by type and severity" />
      </SectionTitle>
      <SectionDescription>
        Detailed analysis of data quality issues detected at the row level,
        including outliers, null values, and data inconsistencies
      </SectionDescription>

      {/* Filter Section */}
      <FilterContainer>
        <FilterLabel>
          <Filter size={16} />
          Filter by Severity:
        </FilterLabel>
        <FilterBtn
          $active={selectedSeverity === "all"}
          onClick={() => setSelectedSeverity("all")}
        >
          All ({rowLevelIssues.length})
        </FilterBtn>
        {severityCounts.critical > 0 && (
          <FilterBtn
            $active={selectedSeverity === "critical"}
            onClick={() => setSelectedSeverity("critical")}
          >
            Critical ({severityCounts.critical})
          </FilterBtn>
        )}
        {severityCounts.warning > 0 && (
          <FilterBtn
            $active={selectedSeverity === "warning"}
            onClick={() => setSelectedSeverity("warning")}
          >
            Warning ({severityCounts.warning})
          </FilterBtn>
        )}
        {severityCounts.info > 0 && (
          <FilterBtn
            $active={selectedSeverity === "info"}
            onClick={() => setSelectedSeverity("info")}
          >
            Info ({severityCounts.info})
          </FilterBtn>
        )}
      </FilterContainer>

      {/* Statistics Cards */}
      {issueSummary && (
        <StatsContainer>
          <StatBox $color="#6366f1" whileHover={{ scale: 1.02 }}>
            <StatNumber $color="#6366f1">
              {issueSummary.total_issues || 0}
            </StatNumber>
            <StatName>
              Total Issues
              <TooltipIcon text="Complete count of all data quality issues found across all rows" />
            </StatName>
          </StatBox>

          {issueSummary.by_type &&
            Object.entries(issueSummary.by_type).map(([type, count]) => (
              <StatBox key={type} $color="#10b981" whileHover={{ scale: 1.02 }}>
                <StatNumber $color="#10b981">{count}</StatNumber>
                <StatName>
                  {type.replace(/_/g, " ")} Issues
                  <TooltipIcon
                    text={`Number of ${type.replace(/_/g, " ")} issues: ${
                      type === "outlier"
                        ? "Values significantly different from normal patterns"
                        : "Missing or null values"
                    }`}
                  />
                </StatName>
              </StatBox>
            ))}
        </StatsContainer>
      )}

      {/* Issue Charts */}
      {(issuesByType.length > 0 || issuesBySeverity.length > 0) && (
        <ChartsSection>
          <ChartsGrid $columns="1fr 1fr">
            {issuesByType.length > 0 && (
              <RechartsPieChart
                data={issuesByType}
                nameKey="name"
                valueKey="value"
                title="Issues by Type"
                height={350}
              />
            )}
            {issuesBySeverity.length > 0 && (
              <RechartsPieChart
                data={issuesBySeverity}
                nameKey="name"
                valueKey="value"
                title="Issues by Severity"
                height={350}
              />
            )}
          </ChartsGrid>
        </ChartsSection>
      )}

      {/* Issues Table */}
      {filteredIssues.length === 0 ? (
        <EmptyState
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <EmptyIcon>✓</EmptyIcon>
          <div>No issues found for the selected severity level</div>
        </EmptyState>
      ) : (
        <TableContainer>
          <Table>
            <Thead>
              <tr>
                <Th>Row #</Th>
                <Th>Column</Th>
                <Th>Issue Type</Th>
                <Th>Severity</Th>
                <Th>Details</Th>
                <Th>Actions</Th>
              </tr>
            </Thead>
            <Tbody>
              <AnimatePresence>
                {filteredIssues.map((issue, index) => (
                  <React.Fragment key={index}>
                    <Tr
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <Td>
                        <strong>{issue.row_index ?? "N/A"}</strong>
                      </Td>
                      <Td>
                        <code
                          style={{
                            background: "#f1f3f4",
                            padding: "4px 8px",
                            borderRadius: "4px",
                            fontWeight: "600",
                          }}
                        >
                          {issue.column}
                        </code>
                      </Td>
                      <Td>
                        <IssueTypeBadge>
                          {issue.issue_type || "unknown"}
                        </IssueTypeBadge>
                      </Td>
                      <Td>
                        <SeverityBadge $severity={issue.severity}>
                          {issue.severity}
                        </SeverityBadge>
                      </Td>
                      <Td>{issue.message || "No additional details"}</Td>
                      <Td>
                        <ExpandBtn onClick={() => toggleRow(index)}>
                          {expandedRows.has(index) ? (
                            <>
                              <ChevronUp size={16} />
                              Hide
                            </>
                          ) : (
                            <>
                              <ChevronDown size={16} />
                              View
                            </>
                          )}
                        </ExpandBtn>
                      </Td>
                    </Tr>

                    <AnimatePresence>
                      {expandedRows.has(index) && (
                        <DetailsRow
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                        >
                          <DetailsCell colSpan={6}>
                            <DetailsGrid>
                              {issue.value !== undefined && (
                                <DetailItem>
                                  <DetailLabel>
                                    Value
                                    <TooltipIcon text="The actual value that triggered this issue" />
                                  </DetailLabel>
                                  <DetailValue>
                                    {String(issue.value)}
                                  </DetailValue>
                                </DetailItem>
                              )}
                              {issue.bounds && (
                                <>
                                  <DetailItem>
                                    <DetailLabel>
                                      Lower Bound
                                      <TooltipIcon text="Minimum acceptable value (values below this are outliers)" />
                                    </DetailLabel>
                                    <DetailValue>
                                      {issue.bounds.lower ?? "N/A"}
                                    </DetailValue>
                                  </DetailItem>
                                  <DetailItem>
                                    <DetailLabel>
                                      Upper Bound
                                      <TooltipIcon text="Maximum acceptable value (values above this are outliers)" />
                                    </DetailLabel>
                                    <DetailValue>
                                      {issue.bounds.upper ?? "N/A"}
                                    </DetailValue>
                                  </DetailItem>
                                </>
                              )}
                              {Object.entries(issue).map(([key, value]) => {
                                if (
                                  ![
                                    "row_index",
                                    "column",
                                    "issue_type",
                                    "severity",
                                    "message",
                                    "value",
                                    "bounds",
                                  ].includes(key) &&
                                  value !== null &&
                                  value !== undefined
                                ) {
                                  return (
                                    <DetailItem key={key}>
                                      <DetailLabel>
                                        {key.replace(/_/g, " ")}
                                      </DetailLabel>
                                      <DetailValue>
                                        {typeof value === "object"
                                          ? JSON.stringify(value, null, 2)
                                          : String(value)}
                                      </DetailValue>
                                    </DetailItem>
                                  );
                                }
                                return null;
                              })}
                            </DetailsGrid>
                          </DetailsCell>
                        </DetailsRow>
                      )}
                    </AnimatePresence>
                  </React.Fragment>
                ))}
              </AnimatePresence>
            </Tbody>
          </Table>
        </TableContainer>
      )}
    </Section>
  );
};

export default RowLevelIssuesSection;
