<?xml version="1.0" encoding="UTF-8"?>
<!--
  WDI Reusable MapForce Helper Function Library (XSLT 2.0 / 3.0).
  Can be imported directly into Altova MapForce via:
    Component -> Import XSLT 2.0 / XQuery Function Library... -> select wdi_helpers.xslt
  
  Functions declared here become visual components under the "wdi_helpers" library in MapForce.
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions"
    xmlns:wdi="http://wdi.mannheim.de/drug-integration/helpers"
    exclude-result-prefixes="xs fn wdi">

    <!-- ===================================================================== -->
    <!-- Lookup tables (relative paths to ../lookups/*.xml)                    -->
    <!-- ===================================================================== -->
    <xsl:variable name="regulatoryStatusDoc" select="document('../lookups/regulatory_status.xml')"/>
    <xsl:variable name="productClassDoc" select="document('../lookups/product_class.xml')"/>
    <xsl:variable name="dosageFormDoc" select="document('../lookups/dosage_form.xml')"/>
    <xsl:variable name="routeDoc" select="document('../lookups/route.xml')"/>
    <xsl:variable name="strengthUnitDoc" select="document('../lookups/strength_unit.xml')"/>

    <!-- ===================================================================== -->
    <!-- Generic String Helpers                                                -->
    <!-- ===================================================================== -->
    <xsl:function name="wdi:cleanText" as="xs:string">
        <xsl:param name="s" as="xs:string?"/>
        <xsl:sequence select="upper-case(normalize-space(string($s)))"/>
    </xsl:function>

    <xsl:function name="wdi:beforeOrSelf" as="xs:string">
        <xsl:param name="s" as="xs:string?"/>
        <xsl:param name="delim" as="xs:string"/>
        <xsl:choose>
            <xsl:when test="contains($s, $delim)">
                <xsl:sequence select="substring-before($s, $delim)"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="string($s)"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:firstWord" as="xs:string">
        <xsl:param name="s" as="xs:string?"/>
        <xsl:sequence select="wdi:beforeOrSelf(normalize-space(string($s)), ' ')"/>
    </xsl:function>

    <xsl:function name="wdi:firstNumber" as="xs:string?">
        <xsl:param name="s" as="xs:string?"/>
        <xsl:variable name="tokens" select="tokenize(concat('0 ', string($s)), '[^0-9.]+')"/>
        <xsl:variable name="cand" select="if (count($tokens) &gt; 1) then $tokens[2] else ''"/>
        <xsl:sequence select="if (matches($cand, '^[0-9]*\.?[0-9]+$')) then $cand else ()"/>
    </xsl:function>

    <!-- ===================================================================== -->
    <!-- Lookups                                                               -->
    <!-- ===================================================================== -->
    <xsl:function name="wdi:stdRegulatoryStatus" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="key" select="wdi:cleanText($raw)"/>
        <xsl:variable name="entry" select="$regulatoryStatusDoc/lookup/entry[@raw = $key]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:sequence select="if ($entry/@std != '') then string($entry/@std) else ()"/>
            </xsl:when>
            <xsl:when test="$key != ''">
                <xsl:sequence select="$key"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:bestRegulatoryStatus" as="xs:string?">
        <xsl:param name="values" as="xs:string?"/>
        <xsl:variable name="tokens" select="tokenize(string($values), ';')"/>
        <xsl:variable name="sortKeys" as="xs:string*">
            <xsl:for-each select="$tokens">
                <xsl:variable name="k" select="wdi:cleanText(.)"/>
                <xsl:variable name="e" select="$regulatoryStatusDoc/lookup/entry[@raw = $k]"/>
                <xsl:if test="$e/@sortKey">
                    <xsl:sequence select="string($e/@sortKey)"/>
                </xsl:if>
            </xsl:for-each>
        </xsl:variable>
        <xsl:choose>
            <xsl:when test="exists($sortKeys)">
                <xsl:variable name="minKey" select="fn:sort($sortKeys)[1]"/>
                <xsl:sequence select="substring-after($minKey, '-')"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:stdProductClass" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="key" select="wdi:cleanText($raw)"/>
        <xsl:variable name="entry" select="$productClassDoc/lookup/entry[@raw = $key]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:sequence select="if ($entry/@std != '') then string($entry/@std) else ()"/>
            </xsl:when>
            <xsl:when test="$key != ''">
                <xsl:sequence select="$key"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:stdDosageForm" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="key" select="wdi:cleanText($raw)"/>
        <xsl:variable name="entry" select="$dosageFormDoc/lookup/entry[@raw = $key]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:sequence select="if ($entry/@std != '') then string($entry/@std) else ()"/>
            </xsl:when>
            <xsl:when test="$key != ''">
                <xsl:sequence select="$key"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:dosageFormList" as="xs:string?">
        <xsl:param name="values" as="xs:string?"/>
        <xsl:variable name="tokens" select="tokenize(string($values), ';')"/>
        <xsl:variable name="mapped" as="xs:string*">
            <xsl:for-each select="$tokens">
                <xsl:variable name="m" select="wdi:stdDosageForm(.)"/>
                <xsl:if test="exists($m) and $m != ''">
                    <xsl:for-each select="tokenize($m, ';')">
                        <xsl:variable name="trimmed" select="normalize-space(.)"/>
                        <xsl:if test="$trimmed != ''">
                            <xsl:sequence select="$trimmed"/>
                        </xsl:if>
                    </xsl:for-each>
                </xsl:if>
            </xsl:for-each>
        </xsl:variable>
        <xsl:variable name="distinct" select="fn:distinct-values($mapped)"/>
        <xsl:choose>
            <xsl:when test="exists($distinct)">
                <xsl:sequence select="string-join(fn:sort($distinct), '; ')"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:stdRoute" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="key" select="wdi:cleanText($raw)"/>
        <xsl:variable name="entry" select="$routeDoc/lookup/entry[@raw = $key]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:sequence select="if ($entry/@std != '') then string($entry/@std) else ()"/>
            </xsl:when>
            <xsl:when test="$key != ''">
                <xsl:sequence select="$key"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:routeList" as="xs:string?">
        <xsl:param name="values" as="xs:string?"/>
        <xsl:variable name="tokens" select="tokenize(translate(string($values), ',', ';'), ';')"/>
        <xsl:variable name="mapped" as="xs:string*">
            <xsl:for-each select="$tokens">
                <xsl:variable name="m" select="wdi:stdRoute(.)"/>
                <xsl:if test="exists($m) and $m != ''">
                    <xsl:for-each select="tokenize($m, ';')">
                        <xsl:variable name="trimmed" select="normalize-space(.)"/>
                        <xsl:if test="$trimmed != ''">
                            <xsl:sequence select="$trimmed"/>
                        </xsl:if>
                    </xsl:for-each>
                </xsl:if>
            </xsl:for-each>
        </xsl:variable>
        <xsl:variable name="distinct" select="fn:distinct-values($mapped)"/>
        <xsl:choose>
            <xsl:when test="exists($distinct)">
                <xsl:sequence select="string-join(fn:sort($distinct), '; ')"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:stdUnit" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="key" select="wdi:cleanText($raw)"/>
        <xsl:variable name="entry" select="$strengthUnitDoc/lookup/entry[@raw = $key]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:sequence select="if ($entry/@std != '') then string($entry/@std) else ()"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:function name="wdi:stdAtcCode" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="tokens" select="tokenize(string($raw), ';')"/>
        <xsl:variable name="cleaned" as="xs:string*">
            <xsl:for-each select="$tokens">
                <xsl:variable name="c" select="translate(wdi:cleanText(.), '*', '')"/>
                <xsl:if test="$c != '' and $c != 'NOT YET ASSIGNED' and $c != 'UNASSIGN'">
                    <xsl:sequence select="if ($c = 'VO4D') then 'V04D' else $c"/>
                </xsl:if>
            </xsl:for-each>
        </xsl:variable>
        <xsl:variable name="distinct" select="fn:distinct-values($cleaned)"/>
        <xsl:choose>
            <xsl:when test="exists($distinct)">
                <xsl:sequence select="string-join(fn:sort($distinct), '; ')"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <!-- ===================================================================== -->
    <!-- FDA Form Splitting                                                    -->
    <!-- ===================================================================== -->
    <xsl:function name="wdi:fdaFormPart" as="xs:string?">
        <xsl:param name="form" as="xs:string?"/>
        <xsl:sequence select="wdi:beforeOrSelf($form, ';')"/>
    </xsl:function>

    <xsl:function name="wdi:fdaRoutePart" as="xs:string?">
        <xsl:param name="form" as="xs:string?"/>
        <xsl:sequence select="substring-after(string($form), ';')"/>
    </xsl:function>

    <!-- ===================================================================== -->
    <!-- Strength Splitting                                                    -->
    <!-- ===================================================================== -->
    <xsl:function name="wdi:strengthCore" as="xs:string">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="s1" select="translate(wdi:cleanText($raw), ',', '')"/>
        <xsl:variable name="s2" select="wdi:beforeOrSelf($s1, '**')"/>
        <xsl:variable name="s3" select="wdi:beforeOrSelf($s2, '(')"/>
        <xsl:sequence select="normalize-space($s3)"/>
    </xsl:function>

    <xsl:function name="wdi:strengthValue" as="xs:decimal?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="core" select="wdi:strengthCore($raw)"/>
        <xsl:variable name="numRaw" select="wdi:beforeOrSelf($core, '/')"/>
        <xsl:if test="not(matches($numRaw, '\d+([.,]\d+)?\s*[A-Za-z%]*\s*(to|[-–—])\s*\d+([.,]\d+)?', 'i'))">
            <xsl:variable name="v" select="wdi:firstNumber($numRaw)"/>
            <xsl:if test="exists($v)">
                <xsl:variable name="rest" select="normalize-space(substring-after($core, $v))"/>
                <xsl:variable name="numerator" select="wdi:beforeOrSelf($rest, '/')"/>
                <xsl:variable name="denominator" select="substring-after($rest, '/')"/>
                <xsl:variable name="q" select="wdi:firstNumber($denominator)"/>
                <xsl:variable name="denUnit" select="if (exists($q)) then substring-after($denominator, $q) else $denominator"/>
                <xsl:variable name="nu" select="wdi:stdUnit(wdi:firstWord($numerator))"/>
                <xsl:variable name="du" select="wdi:stdUnit(wdi:firstWord($denUnit))"/>
                <xsl:variable name="isComboRatio" select="($nu = $du) and exists($q) and ($nu = ('mg', 'g', 'mcg', 'kg', 'mEq', 'U', 'IU'))"/>
                <xsl:choose>
                    <xsl:when test="exists($q) and xs:decimal($q) &gt; 0 and not($isComboRatio)">
                        <xsl:sequence select="round((xs:decimal($v) div xs:decimal($q)) * 1000000) div 1000000"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:sequence select="xs:decimal($v)"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:if>
        </xsl:if>
    </xsl:function>

    <xsl:function name="wdi:strengthUnit" as="xs:string?">
        <xsl:param name="raw" as="xs:string?"/>
        <xsl:variable name="core" select="wdi:strengthCore($raw)"/>
        <xsl:variable name="numRaw" select="wdi:beforeOrSelf($core, '/')"/>
        <xsl:if test="not(matches($numRaw, '\d+([.,]\d+)?\s*[A-Za-z%]*\s*(to|[-–—])\s*\d+([.,]\d+)?', 'i'))">
            <xsl:variable name="v" select="wdi:firstNumber($numRaw)"/>
            <xsl:if test="exists($v)">
                <xsl:variable name="rest" select="normalize-space(substring-after($core, $v))"/>
                <xsl:variable name="numerator" select="wdi:beforeOrSelf($rest, '/')"/>
                <xsl:variable name="denominator" select="substring-after($rest, '/')"/>
                <xsl:variable name="q" select="wdi:firstNumber($denominator)"/>
                <xsl:variable name="denUnit" select="if (exists($q)) then substring-after($denominator, $q) else $denominator"/>
                <xsl:variable name="nu" select="wdi:stdUnit(wdi:firstWord($numerator))"/>
                <xsl:variable name="du" select="if (wdi:stdUnit(wdi:firstWord($denUnit))) then wdi:stdUnit(wdi:firstWord($denUnit)) else lower-case(wdi:firstWord($denUnit))"/>
                <xsl:variable name="isComboRatio" select="($nu = $du) and exists($q) and ($nu = ('mg', 'g', 'mcg', 'kg', 'mEq', 'U', 'IU'))"/>
                <xsl:choose>
                    <xsl:when test="exists($nu) and string-length($du) &gt; 0 and not($isComboRatio)">
                        <xsl:sequence select="concat($nu, '/', $du)"/>
                    </xsl:when>
                    <xsl:when test="exists($nu)">
                        <xsl:sequence select="$nu"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:sequence select="()"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:if>
        </xsl:if>
    </xsl:function>

</xsl:stylesheet>
